"""RT-3 counterexample: Sense drops the fidelity half, hard-coding divergent=False -- so a diverged-but-green
cycle is read as a clean success."""

from recurvelib.completeness import completeness_report
from recurvelib.controller import Progress


def sense(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    report = completeness_report(surface, covered_ids, deferred_ids)
    progress = Progress(
        open=gate_counts.get("open", 0), regressed=gate_counts.get("regressed", 0),
        broken=gate_counts.get("broken", 0), uncovered=report.uncovered,
        divergent=False,                                          # BUG: fidelity dropped
    )
    return progress, report.frontier
