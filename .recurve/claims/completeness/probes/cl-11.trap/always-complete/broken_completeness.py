"""CL-11 counterexample: a report that always declares the cycle complete, even with uncovered surface."""

from recurvelib.completeness import CompletenessReport
from recurvelib.frontier import compute_frontier


def completeness_report(surface, covered, deferred_ids=()):
    fr = compute_frontier(surface, covered, deferred_ids)
    return CompletenessReport(
        frontier=fr.frontier,
        covered=fr.covered,
        deferred=fr.deferred,
        uncovered=fr.uncovered,
        total=fr.total,
        complete=True,  # BUG: complete regardless of the frontier
    )
