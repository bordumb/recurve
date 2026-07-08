"""SOLV-7 counterexample: ignores refute_attempt/restate_attempt entirely and tries the
node's ORIGINAL (known-false) framing directly — the exact mistake refute-first exists to
prevent (proving a statement that's wrong as stated, rather than fixing the framing)."""


def solve(root_id, ctx):
    direct = ctx.close_attempt(root_id, ctx)  # BUG: no refute/restate check first
    if direct is not None:
        return
    ctx.cut_proposer(root_id, ctx)
