"""SUFF-1 counterexample: check_source that forgets to thread explicit_args into the pin
call — the exact bug that produced `Check.lean:18:2: error: Type mismatch` while cutting
the Hs crux's Route-B squared-lintegral step this session."""


def check_source(cut):
    hyps = "".join(f"\n    ({leaf.hypothesis_name} : {leaf.statement})" for leaf in cut.leaves)
    args = " ".join(leaf.hypothesis_name for leaf in cut.leaves)  # BUG: drops cut.explicit_args
    return (
        f"example{hyps} :\n"
        f"    {cut.goal_statement} :=\n"
        f"  {cut.theorem_name} {args}\n"
    )
