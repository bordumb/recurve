"""CL-10 counterexample: coverage aggregation that ignores the `covers` fields, reporting nothing covered
(so the whole surface always looks uncovered — noise that hides the real frontier)."""


def covered_ids(claims):
    return set()  # BUG: never reads claim["covers"]
