"""CL-5 counterexample: a frontier that dedupes the surface by id, erasing a real uncovered point from
the accounting. Passes cl-1/2/3 (their fixtures have all-distinct ids)."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    covered = set(covered_ids)
    deferred = set(deferred_ids)
    seen = {}
    for p in surface:
        seen[p.id] = p  # BUG: collapses distinct same-id points into one
    points = list(seen.values())
    cov = sum(1 for p in points if p.id in covered)
    dfr = sum(1 for p in points if p.id not in covered and p.id in deferred)
    frontier = [p for p in points if p.id not in covered and p.id not in deferred]
    frontier.sort(key=lambda p: (-p.weight, p.id))
    return FrontierReport(
        frontier=tuple(frontier),
        covered=cov,
        deferred=dfr,
        uncovered=len(frontier),
        total=len(points),
    )
