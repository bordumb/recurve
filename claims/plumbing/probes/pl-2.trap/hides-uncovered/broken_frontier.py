"""BROKEN counterexample for PL-2: a frontier surface that reports nothing
uncovered. It would tell the loop the surface is fully covered when it is not —
the silent hole the completeness layer exists to prevent."""


def frontier_ids(surface, covered_ids, deferred_ids=()):
    return []
