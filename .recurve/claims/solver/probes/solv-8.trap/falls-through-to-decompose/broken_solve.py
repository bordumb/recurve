"""SOLV-8 counterexample: never consults discover_attempt at all — every node falls straight
through to cut_proposer, so a dry ∃-search would be silently retried as if it were a
decomposable ∀-obligation instead of being surfaced as its own frontier."""

from recurvelib.loop.solver import SolveResult


def solve(root_id, ctx):
    direct = ctx.close_attempt(root_id, ctx)
    if direct is not None:
        return SolveResult(closed=(root_id,), frontier=(), trace=())
    ctx.cut_proposer(root_id, ctx)  # BUG: discover_attempt is never even called
    return SolveResult(closed=(), frontier=(root_id,), trace=())
