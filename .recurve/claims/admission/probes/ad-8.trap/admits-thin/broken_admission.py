"""AD-8 counterexample: admits any all-probe-able goal regardless of min_invariants, so a single perfect
assertion (spine=1,total=1) is ADMITted. Passes AD-4/5/6."""

from recurvelib.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    if total and spine == total:             # BUG: no min_invariants floor
        verdict = Verdict.ADMIT
    elif spine < min_invariants:
        verdict = Verdict.REFUSE_NOT_GATEABLE
    else:
        verdict = Verdict.REFUSE_AND_INTERVIEW
    return AdmissionReport(verdict=verdict, probeable=spine, total=total,
                           gateability=(spine / total if total else 0.0), worklist=worklist(a),
                           min_invariants=min_invariants)
