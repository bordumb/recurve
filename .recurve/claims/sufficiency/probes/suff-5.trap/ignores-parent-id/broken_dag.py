"""SUFF-5 counterexample: children_of ignores WHICH parent covers_claim names — returns
every gap with a non-empty covers_claim regardless of value (an edge-selectivity bug)."""


def children_of(gaps, parent_id):
    return [g for g in gaps if g.covers_claim]  # BUG: doesn't check parent_id is IN covers_claim


def parents_of(gaps, child_id):
    g = next((x for x in gaps if x.id == child_id), None)
    if g is None:
        raise ValueError(f"unknown gap id: {child_id!r}")
    return [p for p in (next((x for x in gaps if x.id == pid), None) for pid in g.covers_claim) if p is not None]
