"""SOLV-1 counterexample: tries DECOMPOSE before CLOSE — the wrong cost order
(docs/plans/autonomous_solver.md §2.2 puts cheap moves first)."""


def solve(root_id, ctx):
    cut = ctx.cut_proposer(root_id, ctx)  # BUG: decompose attempted first
    if cut is not None:
        return
    ctx.close_attempt(root_id, ctx)
