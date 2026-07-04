"""`frontier` — surface the completeness frontier as a callable verb.

An orchestrator (or a human) needs to see what no claim covers, so a green gate
never masks a silent hole. This module is that surface: :func:`frontier_ids`
runs :func:`recurvelib.frontier.compute_frontier` and returns the ranked
uncovered ids. It mirrors the computation exactly — the surface adds no policy
of its own, so the verb can never disagree with the frontier it exposes.
"""
from __future__ import annotations

from recurvelib.analysis.frontier import compute_frontier


def frontier_ids(surface, covered_ids, deferred_ids=()):
    """Return the ranked uncovered ids for a surface.

    A faithful thin mirror of :func:`recurvelib.frontier.compute_frontier`: it
    computes the frontier and returns each frontier point's id in ranked order
    (highest weight first, then id). Same inputs, same ranking — the surface
    never overrides the computation.

    Args:
        surface: Iterable of SurfacePoint — the full claimable surface.
        covered_ids: Iterable of ids a claim demonstrably covers.
        deferred_ids: Iterable of ids explicitly deferred.

    Returns:
        The ranked uncovered ids, highest-risk first.

    Usage:
        frontier_ids(points, covered_ids={"a"}, deferred_ids={"c"})  # -> ["b"]
    """
    return [p.id for p in compute_frontier(surface, covered_ids, deferred_ids).frontier]
