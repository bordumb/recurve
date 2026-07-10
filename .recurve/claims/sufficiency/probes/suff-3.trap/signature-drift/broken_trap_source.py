"""SUFF-3 counterexample: trap_source drops the LAST hypothesis clause from its own
signature — a signature drift that would fail to typecheck once spliced after the real
module's identically-named import (the check's `example` is typed against ONE signature;
the sorried definition standing in for the real one must match it exactly)."""


def theorem_source(cut, proof):
    hyps = "".join(f"\n    ({leaf.hypothesis_name} : {leaf.statement})" for leaf in cut.leaves)
    return f"theorem {cut.theorem_name}{hyps} :\n    {cut.goal_statement} := by\n  {proof}\n"


def trap_source(cut):
    hyps = "".join(f"\n    ({leaf.hypothesis_name} : {leaf.statement})" for leaf in cut.leaves[:-1])  # BUG
    return f"theorem {cut.theorem_name}{hyps} :\n    {cut.goal_statement} := by\n  sorry\n"
