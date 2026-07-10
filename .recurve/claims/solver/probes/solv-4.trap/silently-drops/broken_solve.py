"""SOLV-4 counterexample: a node with no applicable move is silently dropped instead of
surfaced — `frontier` stays empty, so an unattended run would report nothing left to do
while a genuinely stuck obligation sits unrecorded."""

from recurvelib.loop.solver import SolveResult


def solve(root_id, ctx):
    ctx.close_attempt(root_id, ctx)
    ctx.cut_proposer(root_id, ctx)
    # BUG: neither move applied, but nothing gets recorded anywhere
    return SolveResult(closed=(), frontier=(), trace=())
