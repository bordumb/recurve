"""ST-7 counterexample: stops with success on a cycle that only LOOKS green — it drops the broken,
regressed, and divergent guards, so unmeasured/regressing/diverged work is declared done. Passes ST-1..3
because ST-1's fixture zeroes all three at once."""

from recurvelib.controller import Verdict


def decide(history, k=3):
    if not history:
        return Verdict.CONTINUE
    cur = history[-1]
    if cur.open == 0 and cur.uncovered == 0:  # BUG: ignores broken, regressed, divergent
        return Verdict.STOP_SUCCESS
    if len(history) >= k:
        w = history[-k:]
        rem = [p.open + p.uncovered for p in w]
        if rem[0] > 0 and rem[-1] >= rem[0]:
            return Verdict.STOP_REVERT
    return Verdict.CONTINUE
