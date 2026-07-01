"""BROKEN counterexample for PL-2 (found by adversarial review): a frontier that
returns the uncovered ids in surface order, ignoring weight ranking. The frontier
exists to put the highest-risk uncovered point first; an unranked frontier makes
the loop's "what to claim next" pick meaningless."""


def frontier_ids(surface, covered_ids, deferred_ids=()):
    covered, deferred = set(covered_ids), set(deferred_ids)
    return [p.id for p in surface if p.id not in covered and p.id not in deferred]
