"""ST-6 counterexample: pivots whenever stalled, even when already on the best item (a pivot to itself —
churn that masquerades as re-allocation). Correct on start and on a real pivot, so it passes ST-4/5."""

from recurvelib.loop.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, best)
    if stalled:
        return (Verdict.PIVOT, best)  # BUG: pivots even when best == current_id
    return (Verdict.CONTINUE, current_id)
