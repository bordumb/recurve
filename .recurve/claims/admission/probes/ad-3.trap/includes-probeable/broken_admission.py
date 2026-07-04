"""AD-3 counterexample: a worklist that lists every assertion (including probe-able ones) and drops the
named gaps -- a score-like blob, not the actionable diagnostic."""


def worklist(assertions):
    return tuple((a.id, ()) for a in assertions)  # BUG: includes probe-able ids, no gaps
