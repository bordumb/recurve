"""CL-4 counterexample: a frontier sorted by weight only, with no id tiebreak — ties keep input order
(nondeterministic relative to caller input). Passes cl-1/2/3 (their fixtures have distinct weights)."""

from recurvelib.frontier import FrontierReport


def compute_frontier(surface, covered_ids, deferred_ids=()):
    covered = set(covered_ids)
    deferred = set(deferred_ids)
    points = list(surface)
    cov = sum(1 for p in points if p.id in covered)
    dfr = sum(1 for p in points if p.id not in covered and p.id in deferred)
    frontier = [p for p in points if p.id not in covered and p.id not in deferred]
    frontier.sort(key=lambda p: -p.weight)  # BUG: no id tiebreak -> ties preserve input order
    return FrontierReport(
        frontier=tuple(frontier),
        covered=cov,
        deferred=dfr,
        uncovered=len(frontier),
        total=len(points),
    )
