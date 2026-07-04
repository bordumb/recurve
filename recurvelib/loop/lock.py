"""The tree lock — two loops on one tree corrupt each other.

Any operation that sculpts the target tree or runs a promotion ceremony takes
this lock first; a second loop refuses to start. Suites sharing a tree are
federated into one gate instead of run in parallel — the lock is what makes
"instead of" enforceable.

The lock lives in the system temp directory keyed by the resolved tree path
(never inside the tree itself — the tree may be read-only territory). It
records pid + host + start time so a refusal can name its holder. A dead
holder is reclaimed only by an explicit, human-driven steal — automatic
stealing would reintroduce exactly the corruption the lock exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


class LockHeld(RuntimeError):
    """Another loop holds the tree lock."""


@dataclass(frozen=True)
class LockInfo:
    pid: int
    host: str
    started_at: str
    tree: str

    def describe(self) -> str:
        return f"pid {self.pid} on {self.host} since {self.started_at} (tree {self.tree})"


def _lock_path(tree: Path) -> Path:
    digest = hashlib.sha256(str(tree.resolve()).encode()).hexdigest()[:16]
    d = Path(tempfile.gettempdir()) / "recurve-locks"
    d.mkdir(exist_ok=True)
    return d / f"{digest}.lock"


def read_lock(tree: Path) -> LockInfo | None:
    p = _lock_path(tree)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
        return LockInfo(pid=int(raw["pid"]), host=str(raw["host"]),
                        started_at=str(raw["started_at"]), tree=str(raw["tree"]))
    except (ValueError, KeyError, OSError):
        return LockInfo(pid=-1, host="?", started_at="?", tree=str(tree))


class TreeLock:
    """Context manager: acquire on enter, release on exit. Refuses, never waits."""

    def __init__(self, tree: Path):
        self.tree = tree.resolve()
        self.path = _lock_path(self.tree)
        self._held = False

    def acquire(self) -> None:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = read_lock(self.tree)
            raise LockHeld(
                f"tree is locked by {holder.describe() if holder else 'an unknown holder'} "
                f"— a second loop on one tree corrupts both; if the holder is dead, "
                f"a human may run `recurve lock steal`"
            )
        with os.fdopen(fd, "w") as f:
            json.dump({"pid": os.getpid(), "host": socket.gethostname(),
                       "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                       "tree": str(self.tree)}, f)
        self._held = True

    def release(self) -> None:
        if self._held:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._held = False

    def steal(self) -> LockInfo | None:
        """Human-confirmed reclaim of a dead holder's lock. Returns the evicted holder."""
        holder = read_lock(self.tree)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        return holder

    def __enter__(self) -> "TreeLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
