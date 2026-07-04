"""AD-18 counterexample: admitted defined as "not a REFUSE verdict", so it fails OPEN on None or any unknown
verdict -- a malformed report reaches synthesis. Passes AD-14 (only the three real verdicts are fed there)."""

from recurvelib.analysis.admission import Verdict


def admitted(report):
    return (report.verdict is not Verdict.REFUSE_AND_INTERVIEW
            and report.verdict is not Verdict.REFUSE_NOT_GATEABLE)  # BUG: blacklist, fails open
