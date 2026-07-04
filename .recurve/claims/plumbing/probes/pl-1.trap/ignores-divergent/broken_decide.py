"""BROKEN counterexample for PL-1 (found by adversarial review): a decide surface
that reports STOP-SUCCESS whenever open/regressed/broken/uncovered are all zero,
WITHOUT checking divergent. A green-but-divergent cycle (we built the wrong thing)
must be CONTINUE, never STOP-SUCCESS — this impl would stop on a broken intent."""


def verdict_for(open, regressed, broken, uncovered, divergent=False):
    from recurvelib.loop.controller import Progress, decide
    if open == regressed == broken == uncovered == 0:
        return "STOP-SUCCESS"
    return decide([Progress(open, regressed, broken, uncovered, divergent)]).value
