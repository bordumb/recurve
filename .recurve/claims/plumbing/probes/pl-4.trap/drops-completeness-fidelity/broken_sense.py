"""BROKEN counterexample for PL-4: a sense that carries the gate counts but drops
the completeness (uncovered) and fidelity (divergent) signals — reporting 0 / False
regardless. It would let the loop declare STOP-SUCCESS over an uncovered surface or
a diverged build, the exact blind spots the verification layer closes."""


def sense_vector(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    return {
        "open": gate_counts.get("open", 0),
        "regressed": gate_counts.get("regressed", 0),
        "broken": gate_counts.get("broken", 0),
        "uncovered": 0,
        "divergent": False,
    }
