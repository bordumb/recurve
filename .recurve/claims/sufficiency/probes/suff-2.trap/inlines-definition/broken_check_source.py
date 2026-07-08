"""SUFF-2 counterexample: check_source that inlines the assembly theorem's own definition —
this double-declares `theorem_name` once trap-spliced, defeating the trap mechanism (see the
module docstring in recurvelib/analysis/sufficiency.py for why this must never happen)."""


def check_source(cut):
    hyps = "".join(f"\n    ({leaf.hypothesis_name} : {leaf.statement})" for leaf in cut.leaves)
    args = " ".join(leaf.hypothesis_name for leaf in cut.leaves)
    return (
        f"theorem {cut.theorem_name}{hyps} :\n"
        f"    {cut.goal_statement} := by\n"
        f"  sorry\n\n"
        f"example{hyps} :\n"
        f"    {cut.goal_statement} :=\n"
        f"  {cut.theorem_name} {args}\n"
    )
