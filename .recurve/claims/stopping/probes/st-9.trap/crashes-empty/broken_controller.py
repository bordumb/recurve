"""ST-9 counterexample: no empty-frontier guard, so pick_next raises IndexError exactly when the frontier
is exhausted. Passes ST-4..6 (all use a 2-item frontier)."""

from recurvelib.loop.controller import Verdict


def pick_next(frontier, current_id=None, stalled=False):
    best = frontier[0].id  # BUG: crashes on an empty frontier
    if current_id is None:
        return (Verdict.CONTINUE, best)
    if stalled and best != current_id:
        return (Verdict.PIVOT, best)
    return (Verdict.CONTINUE, current_id)
