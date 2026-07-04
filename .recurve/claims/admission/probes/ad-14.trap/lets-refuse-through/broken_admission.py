"""AD-14 counterexample: lets a REFUSE-AND-INTERVIEW goal proceed to synthesis, bypassing the gate."""

from recurvelib.admission import Verdict


def admitted(report):
    return report.verdict in (Verdict.ADMIT, Verdict.REFUSE_AND_INTERVIEW)  # BUG: an un-admitted goal proceeds
