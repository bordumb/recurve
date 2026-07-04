"""AD-10 counterexample: right gap COUNT, wrong gap CONTENT -- every gap mislabeled "unbounded", so the
interview is sent to fix the wrong criterion. Passes AD-3 (which only checks counts)."""


def worklist(assertions):
    return tuple(
        (a.id, tuple("unbounded scope (no enumerable surface)" for _ in a.gaps()))  # BUG: mislabels every gap
        for a in assertions if not a.probeable
    )
