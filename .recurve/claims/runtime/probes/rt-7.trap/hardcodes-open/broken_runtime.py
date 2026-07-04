"""RT-7 counterexample: Sense hardcodes open=0, so a RED world is read green (a false STOP-SUCCESS through
the sensing seam). Passes RT-2/RT-3, which only ever pass open=0."""

from recurvelib.completeness import completeness_report
from recurvelib.controller import Progress
from recurvelib.fidelity import divergent


def sense(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    report = completeness_report(surface, covered_ids, deferred_ids)
    progress = Progress(
        open=0,                                                   # BUG: gate's open ignored
        regressed=gate_counts.get("regressed", 0), broken=gate_counts.get("broken", 0),
        uncovered=report.uncovered, divergent=divergent(goal_counterexamples),
    )
    return progress, report.frontier
