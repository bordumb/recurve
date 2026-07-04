"""RT-16 counterexample: sense_measured marks the whole surface covered instead of tracing the exercises, so
an unexercised point never reaches the frontier."""

from recurvelib.loop.runtime import sense


def sense_measured(gate_counts, surface, exercises, goal_counterexamples, deferred_ids=()):
    surface = list(surface)
    covered = {p.id for p in surface}        # BUG: declares all covered, ignores the exercises
    return sense(gate_counts, surface, covered, goal_counterexamples, deferred_ids)
