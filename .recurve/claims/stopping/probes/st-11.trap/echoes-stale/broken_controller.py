"""ST-11 counterexample (the original bug): echoes a current_id that is no longer on the frontier, telling
the loop to keep working an item that does not exist. Passes ST-4..6 (their current_id is always on-frontier
or None)."""

from recurvelib.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, best)
    if stalled and best != current_id:
        return (Verdict.PIVOT, best)
    return (Verdict.CONTINUE, current_id)  # BUG: returns a stale current_id not on the frontier
