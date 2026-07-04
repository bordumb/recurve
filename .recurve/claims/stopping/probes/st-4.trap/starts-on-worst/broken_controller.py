"""ST-4 counterexample: starts on the lowest-value item instead of the highest. Correct on pivots, so it
passes ST-5/6."""

from recurvelib.loop.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, frontier[-1].id)  # BUG: starts on the worst point
    if stalled and best != current_id:
        return (Verdict.PIVOT, best)
    return (Verdict.CONTINUE, current_id)
