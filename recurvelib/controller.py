"""The stopping controller: stop / revert / pivot, decided by measurement — never by the actor.

Given a per-cycle **progress vector** measured from the gate (claims open/regressed/broken, frontier size,
divergence), the controller emits exactly one *total* verdict so an agent never decides its own doneness.
This is the deterministic "controller" row of the referee hierarchy (``docs/plans/separation-of-refereeing``)
applied to stopping (``docs/plans/stopping-controller.md``): the actor makes changes; the controller, reading
the gate, decides when to stop, revert, or keep going.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    """A controller's total verdict for one cycle."""

    CONTINUE = "CONTINUE"
    STOP_SUCCESS = "STOP-SUCCESS"
    STOP_REVERT = "STOP-REVERT"
    PIVOT = "PIVOT"


@dataclass(frozen=True)
class Progress:
    """One cycle's measured progress — every field read from the gate, never asserted by the actor.

    Args:
        open: Claims still RED (work remaining).
        regressed: Claims that were GREEN and went RED this cycle (thrashing signal).
        broken: Claims that could not be measured (BROKEN).
        uncovered: Frontier size — the completeness signal.
        divergent: A goal-counterexample passed — the fidelity signal (built the wrong thing).
    """

    open: int
    regressed: int
    broken: int
    uncovered: int
    divergent: bool = False


def decide(history: list[Progress], k: int = 3) -> Verdict:
    """Decide the controller verdict from the measured progress history (most recent last).

    Rules (``stopping-controller.md`` §3):
      * ``STOP_SUCCESS`` — the latest cycle is fully green: ``open == regressed == broken == uncovered == 0``
        and not divergent. (threshold-stop)
      * ``STOP_REVERT`` — not converging over the last ``k`` cycles: divergence persisted, OR regressions
        every cycle (thrashing), OR no net reduction in ``open + uncovered`` (flat progress). (non-improvement)
      * ``CONTINUE`` — otherwise; progress is being made.

    ``PIVOT`` is decided per-item by a separate ranking over the frontier and is not produced here.

    Args:
        history: Progress vectors in cycle order, most recent last.
        k: Window length for the non-improvement rules.

    Usage:
        v = decide(history)  # -> Verdict.STOP_SUCCESS / STOP_REVERT / CONTINUE
    """
    if not history:
        return Verdict.CONTINUE

    cur = history[-1]
    if cur.open == 0 and cur.regressed == 0 and cur.broken == 0 and cur.uncovered == 0 and not cur.divergent:
        return Verdict.STOP_SUCCESS

    if len(history) >= k:
        window = history[-k:]
        if all(p.divergent for p in window):
            return Verdict.STOP_REVERT
        if all(p.regressed > 0 for p in window):
            return Verdict.STOP_REVERT
        remaining = [p.open + p.uncovered for p in window]
        if remaining[0] > 0 and remaining[-1] >= remaining[0]:
            return Verdict.STOP_REVERT

    return Verdict.CONTINUE
