"""`sense` — surface the full measured progress vector as a callable verb.

An orchestrator (or a human) needs the *whole* measured vector, not just the
gate counts: completeness (``uncovered``) from the frontier and fidelity
(``divergent``) from the goal-counterexamples belong in the vector the
controller reads. This module is that surface: :func:`sense_vector` runs
:func:`recurvelib.runtime.sense` and returns the assembled Progress as a dict.
It mirrors the runtime exactly — the surface adds no policy of its own, so the
verb can never disagree with the sensor it exposes.
"""
from __future__ import annotations

from .runtime import sense


def sense_vector(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    """Return the full measured progress vector for a target as a dict.

    A faithful thin mirror of :func:`recurvelib.runtime.sense`: it assembles the
    Progress vector — ``open``/``regressed``/``broken`` from the gate,
    ``uncovered`` from the frontier, ``divergent`` from fidelity — and returns
    its fields as a dict. Same inputs, same vector — the surface never overrides
    the sensor. The frontier that ``sense`` also returns is dropped here; this
    verb reports the vector the controller reads.

    Args:
        gate_counts: Mapping with ``open``/``regressed``/``broken`` from the gate.
        surface: Iterable of SurfacePoint — the full claimable surface.
        covered_ids: Iterable of ids a claim demonstrably covers.
        goal_counterexamples: Iterable of GoalCounterexample (the fidelity signal).
        deferred_ids: Iterable of surface ids explicitly deferred.

    Returns:
        A dict with keys ``open``/``regressed``/``broken``/``uncovered``/``divergent``.

    Usage:
        sense_vector({"open": 0, "regressed": 0, "broken": 0}, points, covered, goals)
    """
    progress, _frontier = sense(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids)
    return {
        "open": progress.open,
        "regressed": progress.regressed,
        "broken": progress.broken,
        "uncovered": progress.uncovered,
        "divergent": progress.divergent,
    }
