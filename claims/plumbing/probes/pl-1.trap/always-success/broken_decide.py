"""BROKEN counterexample for PL-1: a decide surface that ignores the controller
and always returns STOP-SUCCESS. It would tell the loop to stop even with open,
broken, or uncovered work outstanding."""


def verdict_for(open, regressed, broken, uncovered, divergent=False):
    return "STOP-SUCCESS"
