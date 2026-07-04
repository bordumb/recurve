"""AD-17 counterexample: checks ESCALATE before ADMIT, so a goal that just re-gated on the final round
([0,2,0]) is thrown out as not-gateable. Passes AD-11/12/13 (none hit the escalate branch wrongly)."""

from recurvelib.analysis.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    if len(h) >= max_rounds:
        w = rem[-max_rounds:]
        if w[-1] >= w[0]:
            return InterviewVerdict.ESCALATE   # BUG: before the ADMIT check
    if rem[-1] == 0:
        return InterviewVerdict.ADMIT
    return InterviewVerdict.CONTINUE
