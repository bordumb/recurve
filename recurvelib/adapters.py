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
import posixpath
import subprocess
from pathlib import Path

from recurvelib.runtime import within_boundary


def _jsonable(obj):
    """Total JSON fallback: dataclasses (e.g. the Progress evidence) become dicts, everything else a string —
    even if the object's own ``__str__`` raises."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    try:
        return str(obj)
    except Exception:
        return f"<unserializable {type(obj).__name__}>"


class BoundaryViolation(Exception):
    """Raised when a patch would write outside the target tree or onto the referee surface."""


class AgentError(Exception):
    """The agent command failed (non-zero exit) or returned output that isn't a valid patch — a controlled
    signal the driver can act on, never a raw JSONDecodeError / CalledProcessError escaping the loop."""


class RestoreError(Exception):
    """A checkpoint sha could not be restored (unknown/unreachable) — a typed failure of the revert path,
    never a raw CalledProcessError."""


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
        written = []  # (path, prior_text_or_None) in write order, for rollback
        try:
            for rel, content in patch.items():
                path = self.root / posixpath.normpath(rel)   # write the path the boundary approved
                prior = path.read_text() if path.is_file() else None
                written.append((path, prior))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        except Exception:
            for path, prior in reversed(written):          # all-or-nothing: undo partial writes on failure
                if prior is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_text(prior)
            raise

    def checkpoint(self):
        """Commit the current tree and return the commit sha — the state a later ``restore`` rolls back to.

        The snapshot commit is unsigned and skips hooks (``--no-gpg-sign --no-verify``): a checkpoint must not
        depend on the host's commit-signing config, and signing a throwaway snapshot is meaningless.
        """
        self._git("add", "-A")
        self._git("commit", "-m", "runtime-checkpoint", "--allow-empty", "--no-verify", "--no-gpg-sign")
        return self._git("rev-parse", "HEAD").strip()

    def restore(self, sha):
        """Hard-reset the working tree back to ``sha`` (a checkpoint), discarding everything after it.

        Raises ``RestoreError`` (not a raw ``CalledProcessError``) if ``sha`` is unknown/unreachable, so the
        revert path fails in a way the driver can catch.
        """
        try:
            self._git("reset", "--hard", sha)
        except subprocess.CalledProcessError as e:
            raise RestoreError(f"could not restore checkpoint {sha!r}: {(e.stderr or '').strip()[:200]}") from e

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
        if out.returncode != 0:
            raise AgentError(f"agent command exited {out.returncode}: {(out.stderr or '').strip()[:200]}")
        text = out.stdout.strip()
        if not text:
            return {}                                    # a clean run that proposed nothing (no change)
        try:
            patch = json.loads(text)
        except json.JSONDecodeError as e:
            raise AgentError(f"agent output was not valid JSON: {e}") from e
        if not isinstance(patch, dict):
            raise AgentError(f"agent patch must be a JSON object, got {type(patch).__name__}")
        return patch
