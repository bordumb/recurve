"""The frontier: the uncovered region of a target's surface.

A *surface point* is a unit that could be claimed. Given the points a claim set demonstrably *covers* and the
points explicitly *deferred*, the **frontier** is exactly the remainder — ranked by weight, highest-risk
first — and coverage accounting is *total*: every point is covered, deferred, or on the frontier, none lost
and none double-counted. The frontier is the visible gap a claim set leaves open; surfacing it is what keeps
a green gate from masking silent holes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfacePoint:
    """One claimable unit of a target's surface.

    Args:
        id: Stable identifier; a point is covered iff its id is in the covered set.
        weight: Risk/value — higher ranks earlier on the frontier.
        kind: Optional category (behavior, entry point, branch, effect, …).
        location: Optional source location, for reporting.

    Usage:
        SurfacePoint("verify_chain", weight=9, kind="behavior")
    """

    id: str
    weight: int = 0
    kind: str = ""
    location: str = ""


@dataclass(frozen=True)
class FrontierReport:
    """The ranked frontier plus total coverage accounting.

    Invariant: ``covered + deferred + uncovered == total`` and ``len(frontier) == uncovered``.

    Args:
        frontier: The ranked uncovered points (highest weight first).
        covered: Count of points a claim covers.
        deferred: Count of points explicitly deferred.
        uncovered: Count of points on the frontier.
        total: The full surface size.
    """

    frontier: tuple
    covered: int
    deferred: int
    uncovered: int
    total: int


def compute_frontier(surface, covered_ids, deferred_ids=()):
    """Compute the ranked frontier and total coverage accounting for a surface.

    A point is on the frontier iff its id is neither covered nor deferred. ``covered`` takes precedence over
    ``deferred`` (a covered point is covered even if also listed deferred — covered is the stronger state).
    The frontier is sorted by descending weight, then id for determinism.

    Args:
        surface: Iterable of SurfacePoint — the full claimable surface.
        covered_ids: Iterable of ids a claim demonstrably covers.
        deferred_ids: Iterable of ids explicitly deferred (out of scope, recorded).

    Usage:
        rep = compute_frontier(points, covered_ids={"a"}, deferred_ids={"b"})
        # rep.frontier — the uncovered points to claim next, highest-risk first.
    """
    covered_ids = set(covered_ids)
    deferred_ids = set(deferred_ids)
    covered = deferred = total = 0
    frontier = []
    for point in surface:
        total += 1
        if point.id in covered_ids:
            covered += 1
        elif point.id in deferred_ids:
            deferred += 1
        else:
            frontier.append(point)
    frontier.sort(key=lambda p: (-p.weight, p.id))
    return FrontierReport(
        frontier=tuple(frontier),
        covered=covered,
        deferred=deferred,
        uncovered=len(frontier),
        total=total,
    )
