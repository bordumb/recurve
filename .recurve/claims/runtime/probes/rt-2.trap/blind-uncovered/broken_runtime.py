"""RT-2 counterexample: Sense drops the completeness half, always reporting uncovered=0 and an empty
frontier -- a real uncovered unit is invisible."""

from recurvelib.controller import Progress
from recurvelib.fidelity import divergent


def sense(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    progress = Progress(
        open=gate_counts.get("open", 0), regressed=gate_counts.get("regressed", 0),
        broken=gate_counts.get("broken", 0), uncovered=0,        # BUG: completeness dropped
        divergent=divergent(goal_counterexamples),
    )
    return progress, ()
