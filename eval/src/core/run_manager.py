"""run_manager.py — the managed-run lifecycle that ties identity, layout, the
per-run audit trail, and the history index together.

A run happens in one of three modes. A fresh managed run gets its own
timestamped directory that never collides, records itself, relinks `latest`,
and appends to the experiment's index. A continuation extends an existing run in
place (the resumable runner does the real work of adding only the not-yet-sealed
cells) and appends a continuation entry, warning if it is now running under a
different commit or oracle environment than the run started under. The
unmanaged `--out` escape hatch bypasses all of this. The decision and
audit-writing logic lives here so the CLI stays thin, and so it can be tested
without a real clock or git by passing time and commit in at the boundary.
"""

from __future__ import annotations

import hashlib
import os
from datetime import timezone
from pathlib import Path

from src.core import run_id as _run_id
from src.core import run_index, run_meta, run_paths


def iso_utc(dt) -> str:
    """A stable ISO-8601 UTC timestamp for the audit trail."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def manifest_hash(text: str) -> str:
    """Content hash of a frozen manifest, so a run records exactly which config
    produced it."""
    return hashlib.sha256(text.encode()).hexdigest()


def continuation_warnings(meta: run_meta.RunMeta, git_commit: str,
                          oracle_env_hash: str | None) -> list[str]:
    """The advisory warnings for continuing `meta`'s run right now: one if the
    current commit differs from the one the run started under, one if the oracle
    environment differs from the run's first batch. Advisory only — a caller
    who knows why (a pure refactor, say) still proceeds."""
    warns: list[str] = []
    if git_commit != meta.git_commit:
        warns.append(
            f"continuing a run started at commit {meta.git_commit}, current HEAD "
            f"is {git_commit} -- cells added now are graded under different code "
            f"than the ones already sealed")
    start_oracle = meta.continuations[0].oracle_env_hash if meta.continuations else None
    if start_oracle is not None and oracle_env_hash is not None and oracle_env_hash != start_oracle:
        warns.append(
            f"continuing a run started under oracle env {start_oracle}, current "
            f"is {oracle_env_hash} -- cells added now are graded under a different "
            f"oracle than the ones already sealed")
    return warns


def relink_latest(experiments_root: Path, name: str, run_id_str: str) -> None:
    """Point the experiment's `latest` symlink at `run_id_str` (relative, so the
    tree is relocatable), replacing any existing link."""
    link = run_paths.latest_link(experiments_root, name)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(run_id_str)


def resolve_continue_target(experiments_root: Path, name: str, ref: str) -> Path:
    """The run directory `--continue <ref>` names: `latest` follows the symlink;
    otherwise `ref` is a run id under this experiment. Raises FileNotFoundError
    if the run does not exist (never silently starts a new one)."""
    runs = run_paths.runs_root(experiments_root, name)
    if ref == "latest":
        link = run_paths.latest_link(experiments_root, name)
        if not link.is_symlink():
            raise FileNotFoundError(f"experiment {name!r} has no 'latest' run to continue")
        target = os.readlink(link)
        rd = Path(target) if os.path.isabs(target) else runs / target
        if not rd.is_dir():
            raise FileNotFoundError(f"'latest' for {name!r} points at a missing run: {target}")
        return rd
    _run_id.parse_run_id(ref)   # a continue target must be a real run id, not a freeform name
    rd = runs / ref
    if not rd.is_dir():
        raise FileNotFoundError(f"experiment {name!r} has no run {ref!r} to continue")
    return rd


def begin_fresh_run(experiments_root: Path, name: str, now, git_commit: str):
    """Create a fresh managed run directory named for this instant and commit.
    `exist_ok=False`: two runs colliding on the same second AND commit fail loud
    rather than silently merging."""
    rid = _run_id.new_run_id(now, git_commit)
    rd = run_paths.run_dir(experiments_root, name, rid)
    rd.mkdir(parents=True, exist_ok=False)
    return rd, rid


def _index_entry(event: str, run_id_str: str, at: str, git_commit: str,
                 oracle_env_hash: str | None, cells_added: int) -> dict:
    return {"event": event, "run_id": run_id_str, "at": at,
            "git_commit": git_commit, "oracle_env_hash": oracle_env_hash,
            "cells_added": cells_added}


def record_fresh(run_dir: Path, experiments_root: Path, name: str, rid, *,
                 now, git_commit: str, adapter_version: str, manifest_hash: str,
                 command: list[str], oracle_env_hash: str | None,
                 sample_n: int | None, cells_added: int) -> run_meta.RunMeta:
    """Write a fresh run's audit trail: its own metadata with the initial batch
    recorded as the first continuation, then relink `latest` and append to the
    index."""
    at = iso_utc(now)
    meta = run_meta.RunMeta(
        run_id=str(rid), created_at=at, git_commit=git_commit,
        adapter_version=adapter_version, manifest_hash=manifest_hash,
        command=list(command),
        continuations=[run_meta.Continuation(
            at=at, git_commit=git_commit, oracle_env_hash=oracle_env_hash,
            requested_sample_n=sample_n, cells_added=cells_added)])
    run_meta.write(run_dir / "run_meta.json", meta)
    relink_latest(experiments_root, name, str(rid))
    run_index.append(run_paths.index_path(experiments_root, name),
                     _index_entry("fresh", str(rid), at, git_commit, oracle_env_hash, cells_added))
    return meta


def record_continuation(run_dir: Path, experiments_root: Path, name: str, *,
                        now, git_commit: str, oracle_env_hash: str | None,
                        sample_n: int | None, cells_added: int) -> run_meta.RunMeta:
    """Append one continuation to an existing run's audit trail and one line to
    the index. `latest` is left where it is — a continuation extends a run, it
    does not make an older run the newest."""
    at = iso_utc(now)
    meta = run_meta.append_continuation(
        run_dir / "run_meta.json",
        run_meta.Continuation(at=at, git_commit=git_commit, oracle_env_hash=oracle_env_hash,
                              requested_sample_n=sample_n, cells_added=cells_added))
    run_index.append(run_paths.index_path(experiments_root, name),
                     _index_entry("continue", meta.run_id, at, git_commit, oracle_env_hash, cells_added))
    return meta
