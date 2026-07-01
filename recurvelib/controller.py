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


def pick_next(frontier, current_id=None, stalled=False):
    """Choose the next item to work — the PIVOT decision, a bandit over the ranked frontier.

    The frontier is ranked highest-value first (``compute_frontier`` sorts by descending weight). With no
    current item, start on the best. When the current item has *stalled* and a higher-value item exists,
    ``PIVOT`` to it — re-allocate effort rather than grind a stuck item. A stalled item that is already the
    best is not abandoned (that is a ``decide()`` REVERT call, not a pivot).

    Args:
        frontier: The ranked uncovered points (highest value first); each has ``.id``.
        current_id: The id of the item currently being worked, or None to start.
        stalled: Whether the current item has stopped making progress.

    Returns:
        ``(Verdict, item_id)`` — ``(CONTINUE, best)`` to start or stay; ``(PIVOT, best)`` to switch.

    Usage:
        verdict, item = pick_next(report.frontier, current_id="X", stalled=True)
    """
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, best)
    if current_id not in {p.id for p in frontier}:
        return (Verdict.PIVOT, best)  # stale: the item we were on is no longer on the frontier — reconcile
    if stalled and best != current_id:
        return (Verdict.PIVOT, best)
    return (Verdict.CONTINUE, current_id)
