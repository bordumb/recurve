"""AD-2 counterexample: a gateability that reports a fixed high number unrelated to how many assertions
are actually probe-able (the vibe-score the gate exists to avoid)."""


def gateability(assertions):
    return 1.0  # BUG: ignores the assertions entirely
