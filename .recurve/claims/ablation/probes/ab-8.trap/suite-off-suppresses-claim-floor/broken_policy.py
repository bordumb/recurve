# A broken effective_governor_tier that lets the suite-wide default win
# unconditionally — a claim's min_governor_tier floor is silently ignored
# whenever the suite default is weaker (e.g. "off"). This is exactly the
# failure AI9 exists to prevent: a claim asserting "this needs a human"
# would silently run under automated-only review.
_GOVERNOR_RANK = {"off": 0, "mechanical": 1, "mechanical_review": 2, "human_required": 3}


def effective_governor_tier(suite_default, min_governor_tier=""):
    # BUG: always returns the suite default, ignoring the floor entirely.
    return suite_default
