"""AD-11 counterexample: the interview never admits -- even a fully probe-able round keeps interviewing."""

from recurvelib.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    # BUG: no ADMIT branch -- a contract is never recognized as done
    if len(h) >= max_rounds:
        w = rem[-max_rounds:]
        if w[-1] >= w[0]:
            return InterviewVerdict.ESCALATE
    return InterviewVerdict.CONTINUE
