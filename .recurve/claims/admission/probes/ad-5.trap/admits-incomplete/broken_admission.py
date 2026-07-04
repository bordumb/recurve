"""AD-5 counterexample: admits as soon as the spine is large enough, ignoring that some assertions are still
vague -- admitting an incomplete contract, the dangerous failure."""

from recurvelib.analysis.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    verdict = Verdict.ADMIT if spine >= min_invariants else Verdict.REFUSE_NOT_GATEABLE  # BUG: ignores remainder
    return AdmissionReport(
        verdict=verdict, probeable=spine, total=total,
        gateability=(spine / total if total else 0.0), worklist=worklist(a), min_invariants=min_invariants,
    )
