"""CL-17 counterexample: a measurer that returns the whole surface as covered regardless of what ran — the
declarative lie measured coverage exists to kill (it would mark an unexercised function covered)."""


def measure_coverage(exercise, surface_ids=None):
    exercise()
    return set(surface_ids or [])  # BUG: claims coverage of everything, exercised or not
