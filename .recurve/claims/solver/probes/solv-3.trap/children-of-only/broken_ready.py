"""SOLV-3 counterexample: the pre-fix readiness check — "all closed" over
`ledger.children_of(parent)` instead of the cut's own EXPECTED child set. While leaves are
still being armed one at a time, `children_of` only sees whichever ones have already reached
the ledger, so after just the first leaf closes it looks (falsely) like every child is
closed — this is the exact race the real fix (checking against `cut_proposer`'s expected ids
instead) closes."""

from recurvelib.core.model import Status, load_ledger


def ready_to_assemble(cut, ctx):
    ledger = load_ledger(ctx.config)
    children = ledger.children_of(cut.parent_id)
    return bool(children) and all(c.status is Status.CLOSED for c in children)
