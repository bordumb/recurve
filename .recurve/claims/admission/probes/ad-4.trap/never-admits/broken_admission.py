"""AD-4 counterexample: never admits, so a fully probe-able good contract is held back forever."""

from recurvelib.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    return AdmissionReport(
        verdict=Verdict.REFUSE_AND_INTERVIEW,  # BUG: refuses even when every assertion is probe-able
        probeable=spine, total=total,
        gateability=(spine / total if total else 0.0), worklist=worklist(a), min_invariants=min_invariants,
    )
