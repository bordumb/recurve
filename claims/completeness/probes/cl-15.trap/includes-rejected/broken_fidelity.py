"""CL-15 counterexample: reports every goal-counterexample id, including the rejected ones — so the revert
reason is polluted with behaviors that did not actually diverge."""


def divergent_ids(goal_counterexamples):
    return [g.id for g in goal_counterexamples]  # BUG: does not filter on accepted
