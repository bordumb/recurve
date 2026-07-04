"""AD-7 counterexample: checks spine==total before the thinness gate, so an EMPTY goal (0==0) is ADMITted
as a perfect contract. Passes AD-4/5/6 (their goals are non-empty)."""

from recurvelib.analysis.admission import AdmissionReport, Verdict, worklist


def admit(assertions, min_invariants=2):
    a = list(assertions)
    total = len(a)
    spine = sum(1 for x in a if x.probeable)
    if spine == total:                       # BUG: empty goal 0==0 -> ADMIT
        verdict = Verdict.ADMIT
    elif spine < min_invariants:
        verdict = Verdict.REFUSE_NOT_GATEABLE
    else:
        verdict = Verdict.REFUSE_AND_INTERVIEW
    return AdmissionReport(verdict=verdict, probeable=spine, total=total,
                           gateability=(spine / total if total else 0.0), worklist=worklist(a),
                           min_invariants=min_invariants)
