"""Context snapshots — the single mechanism that shares committed state with
an isolated reviewer (`docs/plans/ablation-infra.md` AI3, §5).

A `ClaimSnapshot`/`CycleSnapshot` is a `git archive` of a PINNED COMMIT,
extracted into a fresh temp directory — never a live working-directory path.
This structurally excludes the acting agent's live process, its
conversation/reasoning trace, its uncommitted scratch files, and any other
claim's concurrent in-flight state: none of that is ever committed, so none
of it is ever in the archive. One mechanism serves all three consumers (the
governor's mechanical re-execution tier, its review tier, and R2's per-claim
adversary) rather than three ad hoc context-passing schemes.
"""
from __future__ import annotations

import dataclasses
import shutil
import subprocess
import tempfile
from pathlib import Path


class SnapshotError(Exception):
    """A snapshot could not be built — the source must be a clean git repo at
    a resolvable commit. Refuses rather than silently including uncommitted
    state or comparing against a moving target."""


@dataclasses.dataclass(frozen=True)
class ClaimSnapshot:
    root: Path                       # extracted archive root — a fresh temp dir
    commit: str                      # the pinned commit sha this snapshot IS
    claim_id: str
    include_existing_traps: bool


@dataclasses.dataclass(frozen=True)
class CycleSnapshot:
    root: Path
    commit: str
    claim_ids: tuple[str, ...]
    include_existing_traps: bool


def _resolve_commit(repo: Path, ref: str, *, require_clean: bool) -> str:
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
    if status.returncode != 0:
        raise SnapshotError(f"{repo} is not a git working tree: {status.stderr.strip()[:200]}")
    if require_clean and status.stdout.strip():
        raise SnapshotError(
            "the working tree has uncommitted changes — a snapshot is only ever built "
            "from a pinned COMMIT (git archive), never a live working directory; commit, "
            "stash, or pass require_clean=False to build against HEAD's tree regardless "
            "(the archive still excludes the uncommitted diff either way)")
    rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
                         capture_output=True, text=True, timeout=30)
    if rev.returncode != 0:
        raise SnapshotError(f"{ref!r} does not resolve to a commit in {repo}")
    return rev.stdout.strip()


def _archive(repo: Path, commit: str) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="recurve-snapshot-"))
    proc = subprocess.run(["git", "-C", str(repo), "archive", commit],
                          capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise SnapshotError(f"git archive {commit}: {proc.stderr.decode(errors='replace')[:200]}")
    tar = subprocess.run(["tar", "-x", "-C", str(dest)], input=proc.stdout,
                         capture_output=True, timeout=120)
    if tar.returncode != 0:
        raise SnapshotError(f"extracting archive of {commit}: {tar.stderr.decode(errors='replace')[:200]}")
    return dest


def _strip_traps(root: Path, trap_relpaths) -> None:
    for rel in trap_relpaths:
        target = root / rel
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


def build_claim_snapshot(
    repo: Path, ref: str, claim_id: str, *,
    include_existing_traps: bool = False,
    trap_relpaths: tuple[str, ...] = (),
    require_clean: bool = True,
) -> ClaimSnapshot:
    """Build a `ClaimSnapshot` for one claim. `include_existing_traps`
    defaults to False (withhold traps from a refuting adversary — optimize
    for novel blind-spot discovery over rediscovery, §5); pass True (a
    governor's mechanical tier does) to keep them, since re-executing traps
    IS that tier's job."""
    commit = _resolve_commit(repo, ref, require_clean=require_clean)
    root = _archive(repo, commit)
    if not include_existing_traps:
        _strip_traps(root, trap_relpaths)
    return ClaimSnapshot(root=root, commit=commit, claim_id=claim_id,
                         include_existing_traps=include_existing_traps)


def build_cycle_snapshot(
    repo: Path, ref: str, claim_ids, *,
    include_existing_traps: bool = True,
    trap_relpaths: tuple[str, ...] = (),
    require_clean: bool = True,
) -> CycleSnapshot:
    """Build a `CycleSnapshot` for a cycle's newly-green claims.
    `include_existing_traps` defaults to True here — the governor's
    mechanical tier re-executes existing traps; that is its entire job (§5)."""
    commit = _resolve_commit(repo, ref, require_clean=require_clean)
    root = _archive(repo, commit)
    if not include_existing_traps:
        _strip_traps(root, trap_relpaths)
    return CycleSnapshot(root=root, commit=commit, claim_ids=tuple(claim_ids),
                         include_existing_traps=include_existing_traps)
