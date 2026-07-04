"""ST-5 counterexample: never pivots — grinds a stalled lower-value item forever. Correct on start and on
the already-best case, so it passes ST-4/6."""

from recurvelib.loop.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, best)
    return (Verdict.CONTINUE, current_id)  # BUG: never pivots, even when stalled with a better item
