"""AD-15 counterexample: escalates only when the window is non-decreasing THROUGHOUT, so a dip-and-return
history (un-name a check, re-introduce it) interviews forever. Passes AD-11/12/13 (flat and monotone)."""

from recurvelib.analysis.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    if rem[-1] == 0:
        return InterviewVerdict.ADMIT
    if len(h) >= max_rounds:
        w = rem[-max_rounds:]
        if all(w[i + 1] >= w[i] for i in range(len(w) - 1)):  # BUG: throughout, not endpoints
            return InterviewVerdict.ESCALATE
    return InterviewVerdict.CONTINUE
