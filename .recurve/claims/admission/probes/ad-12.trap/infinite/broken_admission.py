"""AD-12 counterexample: the interview never escalates -- a stuck goal is interviewed forever."""

from recurvelib.analysis.admission import InterviewVerdict


def interview_step(history, max_rounds=3):
    h = [list(r) for r in history]
    if not h:
        return InterviewVerdict.CONTINUE
    rem = [sum(1 for a in r if not a.probeable) for r in h]
    if rem[-1] == 0:
        return InterviewVerdict.ADMIT
    # BUG: no escalate -- no-progress loops forever
    return InterviewVerdict.CONTINUE
