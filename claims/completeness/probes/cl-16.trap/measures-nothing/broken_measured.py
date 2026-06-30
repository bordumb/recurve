"""CL-16 counterexample: a measurer that runs the exercise but records nothing — so genuinely-exercised
surface never counts as covered (everything looks like an eternal hole)."""


def measure_coverage(exercise, surface_ids=None):
    exercise()
    return set()  # BUG: never records what ran
