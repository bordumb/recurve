"""SOLV-2 counterexample: closes every leaf but never propagates the closure upward — the
root's own assembly is armed and the leaves close, yet root-completion (§2.5) never fires,
so the root itself is left open forever even though every child is done."""


def solve(root_id, ctx):
    cut = ctx.cut_proposer(root_id, ctx)
    if cut is None:
        return
    ctx.sufficiency_check(cut, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
    for leaf in cut.leaves:
        direct = ctx.close_attempt(leaf.id, ctx)
        if direct is not None:
            ctx.sufficiency_check(direct, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
    # BUG: no close_upward call — root never gets assembled from the now-closed leaves
