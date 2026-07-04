"""AD-9 counterexample: <= instead of < on the thinness gate, so a spine of EXACTLY min_invariants is
refused as not gateable. Passes AD-4/5/6 (spine 3 and 1, never 2)."""

from recurvelib.analysis.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    if spine <= min_invariants:              # BUG: <= refuses a spine == min_invariants
        verdict = Verdict.REFUSE_NOT_GATEABLE
    elif spine == total:
        verdict = Verdict.ADMIT
    else:
        verdict = Verdict.REFUSE_AND_INTERVIEW
    return AdmissionReport(verdict=verdict, probeable=spine, total=total,
                           gateability=(spine / total if total else 0.0), worklist=worklist(a),
                           min_invariants=min_invariants)
