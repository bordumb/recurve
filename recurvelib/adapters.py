"""Adapters that wire the runtime loop to a real git repository and a BYO-agent.

`GitWorld` backs the loop's ``World`` protocol with an actual working tree: it measures via a supplied gate
function, applies a patch **only within the write boundary**, and snapshots/restores through git. `CommandActor`
backs the ``Actor`` protocol by shelling out to an external agent command — the agent stays external and
pluggable (recurve is BYO-agent); the deterministic plumbing around it lives here and is gated.

A *patch* is a mapping ``{relative_path: new_content}`` — deliberately simple, so the write boundary and the
git snapshot/restore are the load-bearing parts, not a diff-format parser.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

from recurvelib.runtime import within_boundary


def _jsonable(obj):
    """Best-effort JSON fallback: dataclasses (e.g. the Progress evidence) become dicts, everything else str."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return str(obj)


class BoundaryViolation(Exception):
    """Raised when a patch would write outside the target tree or onto the referee surface."""


class GitWorld:
    """A ``World`` backed by a git working tree at ``root``.

    Args:
        root: Path to the target repository's working tree (already ``git init``-ed and configured).
        referee_roots: Repo-relative prefixes the actor may never write (e.g. ``["claims/"]``).
        gate_fn: Callable ``root -> Progress`` — the measurement (recurve's gate in production, a fake in tests).
    """

    def __init__(self, root, referee_roots, gate_fn):
        self.root = Path(root)
        self.referee_roots = [str(r) for r in referee_roots]
        self.gate_fn = gate_fn

    def gate(self):
        return self.gate_fn(self.root)

    def apply(self, patch):
        """Apply ``patch`` (``{relpath: content}``) — but only if *every* path is within the write boundary.

        All paths are checked first; if any is out of bounds nothing is written (no partial application) and
        ``BoundaryViolation`` is raised. Relative paths are checked against an empty target root and the
        repo-relative ``referee_roots``, so ``claims/…``, ``..``-escapes, and absolute paths are all refused.
        """
        rels = list(patch)
        if not within_boundary(rels, "", self.referee_roots):
            raise BoundaryViolation(f"patch touches the referee surface or escapes the tree: {rels}")
        for rel, content in patch.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def checkpoint(self):
        """Commit the current tree and return the commit sha — the state a later ``restore`` rolls back to."""
        self._git("add", "-A")
        self._git("commit", "-m", "runtime-checkpoint", "--allow-empty", "--no-verify")
        return self._git("rev-parse", "HEAD").strip()

    def restore(self, sha):
        """Hard-reset the working tree back to ``sha`` (a checkpoint), discarding everything after it."""
        self._git("reset", "--hard", sha)

    def _git(self, *args):
        out = subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True)
        return out.stdout


class CommandActor:
    """An ``Actor`` that shells out to an external agent command (BYO-agent).

    The command receives the failing evidence as JSON on stdin and must print the proposed patch as JSON
    (``{relpath: content}``) on stdout; empty stdout means "no change". The agent behind the command is
    external and pluggable — this class is only the invocation contract.

    Args:
        cmd: The command to run, as an argv list.
    """

    def __init__(self, cmd):
        self.cmd = list(cmd)

    def propose(self, contract, item, evidence):
        payload = json.dumps({"contract": contract, "item": item, "evidence": evidence}, default=_jsonable)
        out = subprocess.run(self.cmd, input=payload, capture_output=True, text=True)
        text = out.stdout.strip()
        return json.loads(text) if text else {}
