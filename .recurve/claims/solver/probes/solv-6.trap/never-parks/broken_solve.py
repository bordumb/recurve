"""SOLV-6 counterexample: reports a node as frontier in the returned SolveResult but never
writes it to the parked store — an unattended run's only durable trace of where the known
part of the problem ends would vanish once the process exits."""

from recurvelib.loop.solver import SolveResult


def solve(root_id, ctx):
    ctx.close_attempt(root_id, ctx)
    ctx.cut_proposer(root_id, ctx)
    # BUG: frontier is reported in-memory only; ctx.parked_root is never written to
    return SolveResult(closed=(), frontier=(root_id,), trace=())
