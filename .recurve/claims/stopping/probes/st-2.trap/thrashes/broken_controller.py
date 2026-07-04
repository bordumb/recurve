"""ST-2 counterexample: a controller missing the flat-progress revert — it continues forever on
non-progress (thrashes). Still stops on green and continues on real progress, so it passes ST-1/3."""

from recurvelib.loop.controller import Verdict


def decide(history, k=3):
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
        # BUG: no flat-progress revert -> non-progress loops forever
    return Verdict.CONTINUE
