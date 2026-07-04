"""CL-23 counterexample: calls an empty surface complete, so a measurement failure (no surface extracted)
presents as a finished, green cycle."""

from recurvelib.completeness import CompletenessReport
from recurvelib.frontier import compute_frontier


def completeness_report(surface, covered, deferred_ids=()):
    fr = compute_frontier(surface, covered, deferred_ids)
    return CompletenessReport(
        frontier=fr.frontier, covered=fr.covered, deferred=fr.deferred,
        uncovered=fr.uncovered, total=fr.total,
        complete=fr.uncovered == 0,  # BUG: total==0 -> 0==0 -> vacuously complete
    )
