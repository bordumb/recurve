"""RT-17 counterexample: sense_measured aggregates coverage with no per-exercise guard, so a raising probe
body crashes Sense and no Progress vector is produced."""

from recurvelib.analysis.measured import measure_coverage
from recurvelib.loop.runtime import sense


def sense_measured(gate_counts, surface, exercises, goal_counterexamples, deferred_ids=()):
    surface = list(surface)
    ids = {p.id for p in surface}
    covered = set()
    for ex in exercises:
        covered |= measure_coverage(ex, ids)                 # BUG: a raising exercise crashes Sense
    return sense(gate_counts, surface, covered, goal_counterexamples, deferred_ids)
