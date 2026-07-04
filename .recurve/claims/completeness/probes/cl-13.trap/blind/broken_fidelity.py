"""CL-13 counterexample: divergence detection that is blind — it never reports divergent, so an accepted
forbidden behavior sails through behind green probes (the intent-level masking sin)."""


def divergent(goal_counterexamples):
    return False  # BUG: never sees an accepted goal-counterexample
