"""CL-6 counterexample: a frontier that counts the SIZES of the covered/deferred input sets rather than
surface hits, so phantom ids inflate the accounting. Passes cl-1/2/3 (their covered ids are all on-surface)."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    covered = set(covered_ids)
    deferred = set(deferred_ids)
    points = list(surface)
    frontier = [p for p in points if p.id not in covered and p.id not in deferred]
    frontier.sort(key=lambda p: (-p.weight, p.id))
    return FrontierReport(
        frontier=tuple(frontier),
        covered=len(covered),  # BUG: counts phantom ids, not surface hits
        deferred=len(deferred),
        uncovered=len(frontier),
        total=len(points),
    )
