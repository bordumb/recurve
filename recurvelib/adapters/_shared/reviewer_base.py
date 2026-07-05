"""Shared reviewer plumbing, written once (`docs/plans/ablation-infra.md` AI11).

Isolation-executor invocation, snapshot construction, and provenance
attachment are wired here exactly once; `adversary/*.py` and `governor/*.py`
adapters compose from `run_claim_reviewer`/`run_cycle_reviewer` rather than
each reimplementing their own copy of "build a snapshot, run it isolated,
stamp a provenance envelope."

`provenance` (AI7) is a `Provenance` envelope — `metadata_verified` by
default when the caller supplies an identity, `unverified` when it doesn't.
A caller wanting `cryptographically_attested` builds that `Provenance`
itself (`_shared.provenance.cryptographically_attested`) and passes it in;
this module never invents a strength stronger than what the caller actually
established.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from recurvelib.adapters.isolation import resolve as resolve_isolation
from recurvelib.adapters.snapshot import build_claim_snapshot, build_cycle_snapshot
from recurvelib.adapters._shared.provenance import Provenance, metadata_verified, unverified


@dataclasses.dataclass(frozen=True)
class ReviewInvocation:
    """The result of one isolated reviewer pass: the isolated process's raw
    result, the pinned snapshot commit it ran against, and a provenance
    envelope every adapter attaches identically (never rolls its own)."""

    returncode: int
    stdout: str
    stderr: str
    snapshot_commit: str
    provenance: Provenance


def _invoke(snap, argv, isolation_strategy: str, image: str | None, timeout: int):
    strat = resolve_isolation(isolation_strategy)
    if isolation_strategy == "docker":
        return strat.run_isolated(snap.root, argv, image, timeout=timeout)
    return strat.run_isolated(snap.root, argv, timeout=timeout)


def _resolve_provenance(provenance: Provenance | None, identity: str | None) -> Provenance:
    if provenance is not None:
        return provenance
    return metadata_verified(identity) if identity else unverified()


def run_claim_reviewer(
    repo, ref, claim_id, argv, *,
    isolation_strategy: str = "subprocess_tempdir",
    include_existing_traps: bool = False,
    trap_relpaths: tuple = (),
    image: str | None = None,
    timeout: int = 300,
    identity: str | None = None,
    provenance: Provenance | None = None,
) -> ReviewInvocation:
    """Build a `ClaimSnapshot` and run `argv` against it under the named
    isolation strategy — the one code path every adversary adapter composes
    from, so isolation/snapshot/provenance wiring is never per-adapter.
    Pass `identity` for a cheap `metadata_verified` stamp, or a pre-built
    `provenance` (e.g. `cryptographically_attested`) for a stronger one."""
    snap = build_claim_snapshot(
        Path(repo), ref, claim_id, include_existing_traps=include_existing_traps,
        trap_relpaths=trap_relpaths)
    result = _invoke(snap, argv, isolation_strategy, image, timeout)
    return ReviewInvocation(
        returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
        snapshot_commit=snap.commit, provenance=_resolve_provenance(provenance, identity))


def run_cycle_reviewer(
    repo, ref, claim_ids, argv, *,
    isolation_strategy: str = "subprocess_tempdir",
    include_existing_traps: bool = True,
    trap_relpaths: tuple = (),
    image: str | None = None,
    timeout: int = 300,
    identity: str | None = None,
    provenance: Provenance | None = None,
) -> ReviewInvocation:
    """Build a `CycleSnapshot` and run `argv` against it — the one code path
    every governor adapter composes from."""
    snap = build_cycle_snapshot(
        Path(repo), ref, claim_ids, include_existing_traps=include_existing_traps,
        trap_relpaths=trap_relpaths)
    result = _invoke(snap, argv, isolation_strategy, image, timeout)
    return ReviewInvocation(
        returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
        snapshot_commit=snap.commit, provenance=_resolve_provenance(provenance, identity))


# --- AI11's lint-shaped check: adapters compose from this module, never their
# --- own copy of subprocess/snapshot logic. Nice-to-have, not a hard gate.

_REIMPLEMENTATION_MARKERS = ("subprocess.run(", "subprocess.Popen(", "git\", \"archive")
_SHARED_IMPORT_MARKERS = ("_shared.reviewer_base", "recurvelib.adapters._shared")
_EXEMPT_FILENAMES = {"__init__.py"}
_EXEMPT_PREFIXES = ("off",)  # a no-op adapter legitimately does nothing


def adapters_not_using_shared(adapters_root) -> list[Path]:
    """Scan `adapters_root/{adversary,governor}/*.py` for a file that
    reimplements subprocess/snapshot plumbing directly instead of importing
    this module. Returns the offending files (empty means clean)."""
    root = Path(adapters_root)
    bad: list[Path] = []
    for sub in ("adversary", "governor"):
        d = root / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            if f.name in _EXEMPT_FILENAMES or f.name.startswith(_EXEMPT_PREFIXES):
                continue
            text = f.read_text()
            reimplements = any(marker in text for marker in _REIMPLEMENTATION_MARKERS)
            uses_shared = any(marker in text for marker in _SHARED_IMPORT_MARKERS)
            if reimplements and not uses_shared:
                bad.append(f)
    return bad
