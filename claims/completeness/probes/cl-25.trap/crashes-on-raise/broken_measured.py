"""CL-25 counterexample: covered_by has no per-exercise guard, so one raising probe body propagates and
aborts the whole aggregate (losing the clean exercises' coverage)."""

from recurvelib.measured import measure_coverage


def covered_by(exercises, surface_ids):
    surface_ids = set(surface_ids)
    covered = set()
    for exercise in exercises:
        covered |= measure_coverage(exercise, surface_ids)   # BUG: a raising exercise crashes the pass
    return covered
