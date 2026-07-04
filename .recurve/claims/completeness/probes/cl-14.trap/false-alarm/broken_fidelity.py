"""CL-14 counterexample: divergence detection that always fires — even with everything rejected it cries
divergent, which would force the controller into endless reverts and block all progress."""


def divergent(goal_counterexamples):
    return True  # BUG: divergent even when nothing forbidden was accepted
