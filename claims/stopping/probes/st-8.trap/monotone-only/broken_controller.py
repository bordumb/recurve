"""ST-8 counterexample: reverts only when the window never once decreased — so dip-and-return oscillation
like [5,1,5] (net zero progress) escapes forever. Passes ST-2 (constant [5,5,5] is non-decreasing) and
ST-3 ([5,3,1] has down-steps, correctly not reverted)."""

from recurvelib.controller import Verdict


def decide(history, k=3):
    if not history:
        return Verdict.CONTINUE
    cur = history[-1]
    if cur.open == 0 and cur.regressed == 0 and cur.broken == 0 and cur.uncovered == 0 and not cur.divergent:
        return Verdict.STOP_SUCCESS
    if len(history) >= k:
        w = history[-k:]
        if all(p.divergent for p in w):
            return Verdict.STOP_REVERT
        if all(p.regressed > 0 for p in w):
            return Verdict.STOP_REVERT
        rem = [p.open + p.uncovered for p in w]
        if rem[0] > 0 and all(rem[i + 1] >= rem[i] for i in range(len(rem) - 1)):  # BUG: monotone-only
            return Verdict.STOP_REVERT
    return Verdict.CONTINUE
