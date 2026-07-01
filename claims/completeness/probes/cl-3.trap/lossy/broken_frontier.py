"""CL-3 counterexample: covered/deferred points are not counted, so the parts don't sum to the total."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    covered = set(covered_ids)
    deferred = set(deferred_ids)
    points = list(surface)
    frontier = [p for p in points if p.id not in covered and p.id not in deferred]
    frontier.sort(key=lambda p: (-p.weight, p.id))
    return FrontierReport(
        frontier=tuple(frontier),
        covered=0,  # BUG: dropped from the accounting
        deferred=0,  # BUG: dropped from the accounting
        uncovered=len(frontier),
        total=len(points),
    )
