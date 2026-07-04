"""CL-2 counterexample: a frontier sorted ascending by weight (lowest-risk first), not descending."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    covered = set(covered_ids)
    deferred = set(deferred_ids)
    points = list(surface)
    cov = sum(1 for p in points if p.id in covered)
    dfr = sum(1 for p in points if p.id not in covered and p.id in deferred)
    frontier = [p for p in points if p.id not in covered and p.id not in deferred]
    frontier.sort(key=lambda p: (p.weight, p.id))  # BUG: ascending -> lowest-risk first
    return FrontierReport(
        frontier=tuple(frontier),
        covered=cov,
        deferred=dfr,
        uncovered=len(frontier),
        total=len(points),
    )
