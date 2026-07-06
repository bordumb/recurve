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

from recurvelib.adapters.boundary import BOUNDARY_ADAPTERS
from recurvelib.adapters.registry import resolve_boundary


def _jsonable(obj):
    """Total JSON fallback: dataclasses (e.g. the Progress evidence) become dicts, everything else a string —
    even if ``asdict`` or the object's own ``__str__`` raises."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return dataclasses.asdict(obj)
        except Exception:
            pass                                  # a recursive/unserializable field -> fall through to str
    try:
        return str(obj)
    except Exception:
        return f"<unserializable {type(obj).__name__}>"


class BoundaryViolation(Exception):
    """Raised when a patch would write outside the target tree or onto the referee surface."""


class GitError(Exception):
    """A git command failed — non-zero exit, a missing/unexecutable git binary, or a timeout."""


class AgentError(Exception):
    """The agent command failed (non-zero exit) or returned output that isn't a valid patch — a controlled
    signal the driver can act on, never a raw JSONDecodeError / CalledProcessError escaping the loop."""


class RestoreError(Exception):
    """A checkpoint sha could not be restored (unknown/unreachable) — a typed failure of the revert path,
    never a raw CalledProcessError."""


class CheckpointError(Exception):
    """A checkpoint (git snapshot) could not be made — git unavailable/failed — a typed failure of the
    snapshot path, symmetric with RestoreError."""


class GitWorld:
    """A ``World`` backed by a git working tree at ``root``.

    Args:
        root: Path to the target repository's working tree (already ``git init``-ed and configured).
        referee_roots: Repo-relative prefixes the actor may never write (e.g. ``["claims/"]``).
        gate_fn: Callable ``root -> Progress`` — the measurement (recurve's gate in production, a fake in tests).
        boundary: BoundaryPort selection — ``"enforced"`` (default, byte-identical to every prior GitWorld)
            or ``"open"``, a deliberately dangerous, off-by-default bypass. Resolved through recurvelib's OWN
            registry (never reimplemented here), so an unknown value fails loud at construction, before the
            first ``apply()``.
    """

    def __init__(self, root, referee_roots, gate_fn, boundary: str = "enforced"):
        self.root = Path(root)
        self.referee_roots = [str(r) for r in referee_roots]
        self.gate_fn = gate_fn
        self.boundary = boundary
        self._boundary_check = resolve_boundary(boundary, BOUNDARY_ADAPTERS)()

    def gate(self):
        return self.gate_fn(self.root)

    def apply(self, patch):
        """Apply ``patch`` (``{relpath: content}``) — but only if *every* path is within the write boundary.

        All paths are checked first; if any is out of bounds nothing is written (no partial application) and
        ``BoundaryViolation`` is raised. Relative paths are checked against an empty target root and the
        repo-relative ``referee_roots``, so ``claims/…``, ``..``-escapes, and absolute paths are all refused —
        UNLESS ``boundary="open"``, which bypasses this check entirely and says so loudly (stderr) on every
        call.
        """
        rels = list(patch)
        if not self._boundary_check.check(rels, "", self.referee_roots):
            raise BoundaryViolation(f"patch touches the referee surface or escapes the tree: {rels}")
        if not all(isinstance(v, str) for v in patch.values()):
            raise BoundaryViolation("patch values must be strings")
        root_resolved = self.root.resolve()
        written = []          # (path, prior_bytes_or_None) in write order — bytes so a binary prior survives
        created_dirs = set()  # directories this apply created, so rollback can remove them
        try:
            for rel, content in patch.items():
                path = self.root / posixpath.normpath(rel)   # write the path the boundary approved
                # follow symlinks in the parent chain: a symlinked prefix must not escape the tree
                resolved_parent = path.parent.resolve()
                if resolved_parent != root_resolved and not str(resolved_parent).startswith(str(root_resolved) + "/"):
                    raise BoundaryViolation(f"path escapes the tree through a symlink: {rel}")
                prior = path.read_bytes() if path.is_file() else None
                written.append((path, prior))
                parent = path.parent
                while str(parent).startswith(str(self.root)) and parent != self.root and not parent.exists():
                    created_dirs.add(parent)
                    parent = parent.parent
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        except Exception:
            for path, prior in reversed(written):          # all-or-nothing: undo partial writes on failure,
                try:                                        # each step guarded so one failure can't leave a mix
                    if prior is None:
                        if path.is_file():                  # only remove a file we wrote, not a pre-existing dir
                            path.unlink()
                    else:
                        path.write_bytes(prior)
                except OSError:
                    pass
            for d in sorted(created_dirs, key=lambda p: len(str(p)), reverse=True):
                try:
                    d.rmdir()                              # deepest-first; only removes if empty
                except OSError:
                    pass
            raise

    def checkpoint(self):
        """Commit the current tree and return the commit sha — the state a later ``restore`` rolls back to.

        The snapshot commit is unsigned and skips hooks (``--no-gpg-sign --no-verify``): a checkpoint must not
        depend on the host's commit-signing config, and signing a throwaway snapshot is meaningless. Raises a
        typed ``CheckpointError`` (never a raw git failure), symmetric with ``restore``'s ``RestoreError``.
        """
        try:
            self._git("add", "-A")
            # supply a throwaway identity via -c, so a checkpoint works on a repo with no configured user.
            self._git("-c", "user.name=recurve", "-c", "user.email=recurve@localhost",
                      "commit", "-m", "runtime-checkpoint", "--allow-empty", "--no-verify", "--no-gpg-sign")
            return self._git("rev-parse", "HEAD").strip()
        except GitError as e:
            raise CheckpointError(f"could not checkpoint: {e}") from e

    def restore(self, sha):
        """Hard-reset the working tree back to ``sha`` (a checkpoint), discarding everything after it.

        Raises ``RestoreError`` (never a raw ``CalledProcessError``/``FileNotFoundError``/timeout) if the sha
        is unknown/unreachable or git is unavailable, so the revert path fails in a way the driver can catch.
        """
        try:
            self._git("reset", "--hard", sha)
        except GitError as e:
            raise RestoreError(f"could not restore checkpoint {sha!r}: {e}") from e

    def _git(self, *args, timeout=60):
        try:
            out = subprocess.run(["git", "-C", str(self.root), *args],
                                 check=True, capture_output=True, text=True, timeout=timeout)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise GitError(f"git {' '.join(args)}: {e}") from e
        return out.stdout


class CommandActor:
    """An ``Actor`` that shells out to an external agent command (BYO-agent).

    The command receives the failing evidence as JSON on stdin and must print the proposed patch as JSON
    (``{relpath: content}``) on stdout; empty stdout means "no change". The agent behind the command is
    external and pluggable — this class is only the invocation contract.

    Args:
        cmd: The command to run, as an argv list.
    """

    def __init__(self, cmd, timeout=300):
        self.cmd = list(cmd)
        self.timeout = timeout

    def propose(self, contract, item, evidence):
        payload = json.dumps({"contract": contract, "item": item, "evidence": evidence}, default=_jsonable)
        try:
            out = subprocess.run(self.cmd, input=payload, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise AgentError(f"agent command timed out after {self.timeout}s") from e
        except OSError as e:
            raise AgentError(f"agent command could not be run: {e}") from e
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
