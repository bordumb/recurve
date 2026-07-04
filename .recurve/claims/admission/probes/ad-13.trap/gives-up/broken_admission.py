"""AD-13 counterexample: the interview escalates the moment the window fills, even while the un-probe-able
set is still shrinking -- it abandons a converging interview."""

from recurvelib.analysis.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    if rem[-1] == 0:
        return InterviewVerdict.ADMIT
    if len(h) >= max_rounds:
        return InterviewVerdict.ESCALATE  # BUG: ignores whether progress is being made
    return InterviewVerdict.CONTINUE
