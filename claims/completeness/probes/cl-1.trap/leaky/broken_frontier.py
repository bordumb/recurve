"""CL-1 counterexample: a frontier that ignores ``covered_ids``, so covered points leak onto the frontier."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    deferred = set(deferred_ids)
    points = list(surface)
    frontier = [p for p in points if p.id not in deferred]  # BUG: covered_ids ignored -> leak
    frontier.sort(key=lambda p: (-p.weight, p.id))
    return FrontierReport(
        frontier=tuple(frontier),
        covered=0,
        deferred=len(deferred),
        uncovered=len(frontier),
        total=len(points),
    )
