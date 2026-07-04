"""ST-3 counterexample: a controller that reverts the moment any open work remains — it abandons a
converging approach. Still stops on green and reverts on flat, so it passes ST-1/2."""

from recurvelib.loop.controller import Verdict


def decide(history, k=3):
    if not history:
        return Verdict.CONTINUE
    cur = history[-1]
    if cur.open == 0 and cur.regressed == 0 and cur.broken == 0 and cur.uncovered == 0 and not cur.divergent:
        return Verdict.STOP_SUCCESS
    if cur.open > 0:  # BUG: gives up on any remaining work, even while it is shrinking
        return Verdict.STOP_REVERT
    return Verdict.CONTINUE
