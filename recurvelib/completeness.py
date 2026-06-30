"""The completeness gate: a release is green only if it is sound AND complete.

*Soundness* is the existing probe gate — every claim's probe passes. *Completeness* is the other half: every
point of the target's surface is either **covered** by a claim or explicitly **deferred**, so nothing is
silently unaddressed. This module ties surface extraction and the frontier to a ledger of claims (each
declaring the surface ids it covers) and reports whether a cycle is complete, plus the ranked frontier of
what it is not.

The coverage *source* is pluggable on purpose. :func:`covered_ids` aggregates **declared** coverage (each
claim's ``covers`` field) — simple, but a claim can declare coverage it does not exercise. A *measured*
source (instrumented probe runs) is the stronger upgrade and slots into the same :func:`completeness_report`
seam without changing it.
"""
from __future__ import annotations

from dataclasses import dataclass

from recurvelib.frontier import compute_frontier


@dataclass(frozen=True)
class CompletenessReport:
    """The frontier plus the completeness verdict for a surface against a ledger.

    Invariant: ``complete`` is True exactly when ``uncovered == 0`` (the frontier is empty).

    Args:
        frontier: The ranked uncovered surface points — the silent holes, made visible.
        covered: Count of surface points a claim covers.
        deferred: Count explicitly deferred.
        uncovered: Frontier size.
        total: The full surface size.
        complete: Whether every surface point is covered or deferred.
    """

    frontier: tuple
    covered: int
    deferred: int
    uncovered: int
    total: int
    complete: bool


def covered_ids(claims) -> set:
    """Aggregate **declared** coverage: the union of every claim's ``covers`` field.

    Args:
        claims: Iterable of claim mappings (e.g. ledger entries), each optionally carrying ``covers`` —
            a list of surface point ids it covers.

    Usage:
        ids = covered_ids(ledger_entries)  # -> {"verify_chain", "Client.open", ...}
    """
    ids: set = set()
    for claim in claims:
        ids.update(claim.get("covers") or [])
    return ids


def completeness_report(surface, covered, deferred_ids=()) -> CompletenessReport:
    """Report the frontier and completeness verdict for ``surface`` against a coverage set.

    Args:
        surface: Iterable of SurfacePoint — the full claimable surface (from ``extract_surface``).
        covered: Iterable of covered surface ids (from :func:`covered_ids`, or a measured source).
        deferred_ids: Iterable of surface ids explicitly deferred.

    Returns:
        A CompletenessReport; ``complete`` is True iff nothing is uncovered.

    Usage:
        rep = completeness_report(surface, covered_ids(claims), deferred_ids=deferred)
        if not rep.complete:
            # rep.frontier is the ranked list of what no claim covers — claim it or defer it.
            ...
    """
    fr = compute_frontier(surface, covered, deferred_ids)
    return CompletenessReport(
        frontier=fr.frontier,
        covered=fr.covered,
        deferred=fr.deferred,
        uncovered=fr.uncovered,
        total=fr.total,
        complete=fr.uncovered == 0,
    )
