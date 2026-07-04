"""AD-6 counterexample: a too-thin spine is sent to interview instead of refused, so the gate tries to gate
a goal that has too few real invariants to be a contract."""

from recurvelib.analysis.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    verdict = Verdict.ADMIT if spine == total else Verdict.REFUSE_AND_INTERVIEW  # BUG: never REFUSE_NOT_GATEABLE
    return AdmissionReport(
        verdict=verdict, probeable=spine, total=total,
        gateability=(spine / total if total else 0.0), worklist=worklist(a), min_invariants=min_invariants,
    )
