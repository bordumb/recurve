"""CL-12 counterexample: a report that empties the frontier and declares completeness — the cardinal sin,
a green gate that silently says nothing about the uncovered surface."""

from recurvelib.analysis.completeness import CompletenessReport
from recurvelib.analysis.frontier import compute_frontier


def completeness_report(surface, covered, deferred_ids=()):
    fr = compute_frontier(surface, covered, deferred_ids)
    return CompletenessReport(
        frontier=(),       # BUG: the uncovered points are hidden
        covered=fr.covered,
        deferred=fr.deferred,
        uncovered=0,       # BUG: and the count is zeroed
        total=fr.total,
        complete=True,
    )
