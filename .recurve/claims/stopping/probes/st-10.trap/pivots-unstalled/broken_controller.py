"""ST-10 counterexample: pivots on rank alone, ignoring `stalled` — so it abandons a healthy in-flight item
every cycle a higher-ranked point exists. Passes ST-4..6 (none exercise stalled=False with a better item)."""

from recurvelib.loop.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    if not frontier:
        return (Verdict.CONTINUE, None)
    best = frontier[0].id
    if current_id is None:
        return (Verdict.CONTINUE, best)
    if best != current_id:  # BUG: ignores stalled
        return (Verdict.PIVOT, best)
    return (Verdict.CONTINUE, current_id)
