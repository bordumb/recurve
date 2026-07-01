"""`decide` — surface the stopping controller as a callable verb.

An orchestrator (or a human) needs to ask for a stop verdict from a *measured*
progress vector rather than let a mechanical cap decide blind. This module is
that surface: :func:`verdict_for` runs :func:`recurvelib.controller.decide` on a
single measured cycle and returns its verdict string. It mirrors the controller
exactly — the surface adds no policy of its own, so the verb can never disagree
with the referee it exposes.
"""
from __future__ import annotations

from .controller import Progress, decide


def verdict_for(open: int, regressed: int, broken: int, uncovered: int, divergent: bool = False) -> str:
    """Return the controller's verdict string for one measured progress vector.

    A faithful thin mirror of :func:`recurvelib.controller.decide`: it wraps the
    vector in a one-cycle history and returns the verdict's ``.value``. Same
    inputs, same decision — the surface never overrides the controller.

    Args:
        open: Claims still RED (work remaining).
        regressed: Claims that were GREEN and went RED this cycle.
        broken: Claims that could not be measured.
        uncovered: Frontier size — the completeness signal.
        divergent: Whether a goal-counterexample passed (fidelity signal).

    Returns:
        The verdict string, one of ``"STOP-SUCCESS"`` / ``"STOP-REVERT"`` /
        ``"CONTINUE"``.

    Usage:
        verdict_for(0, 0, 0, 0)  # -> "STOP-SUCCESS"
    """
    return decide([Progress(open, regressed, broken, uncovered, divergent)]).value
