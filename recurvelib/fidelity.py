"""Intent fidelity: did we build the right thing — not merely a thing that passes its probes?

A probe can pass while the goal is violated: the probe tested the letter, the implementation broke the
intent. Fidelity guards against this with **goal-counterexamples** — behaviors that must *never* be accepted.
If any goal-counterexample is observed accepted, the cycle has **diverged** from intent, no matter how green
the probes are. Divergence is the signal the controller (:mod:`recurvelib.controller`) reads to STOP-REVERT:
soundness and completeness are necessary, but a high-fidelity stop also requires that nothing the goal
forbids has crept in.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoalCounterexample:
    """A behavior the goal forbids — it must stay rejected.

    Args:
        id: Stable identifier for the forbidden behavior.
        accepted: Whether it was observed *accepted* this cycle. True means the build diverged from intent.
        weight: Severity, for reporting/ranking (a higher-weight divergence is more urgent).
    """

    id: str
    accepted: bool
    weight: int = 0


def divergent(goal_counterexamples) -> bool:
    """True iff any goal-counterexample was accepted — green probes but broken intent.

    Args:
        goal_counterexamples: Iterable of GoalCounterexample observed this cycle.

    Usage:
        if divergent(goals):
            progress = Progress(..., divergent=True)  # the controller will STOP-REVERT
    """
    return any(g.accepted for g in goal_counterexamples)


def divergent_ids(goal_counterexamples) -> list:
    """The ids of the accepted goal-counterexamples, highest weight first — what diverged, for the revert.

    Args:
        goal_counterexamples: Iterable of GoalCounterexample observed this cycle.

    Usage:
        divergent_ids(goals)  # -> ["forbidden_bypass", ...] to name in the revert reason
    """
    accepted = [g for g in goal_counterexamples if g.accepted]
    accepted.sort(key=lambda g: (-g.weight, g.id))
    return [g.id for g in accepted]
