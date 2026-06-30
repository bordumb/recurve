"""AD-16 counterexample: takes the no-progress window from the FRONT of the history, so an early stuck
stretch that has since converged is escalated. Passes AD-11/12/13 (all length <= 3, where front==back)."""

from recurvelib.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    if rem[-1] == 0:
        return InterviewVerdict.ADMIT
    if len(h) >= max_rounds:
        w = rem[:max_rounds]  # BUG: first rounds, not the most recent
        if w[-1] >= w[0]:
            return InterviewVerdict.ESCALATE
    return InterviewVerdict.CONTINUE
