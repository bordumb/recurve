# solver — the move-typed recursion, probed

> `recurvelib/loop/solver.py` (`docs/plans/autonomous_solver.md` §2): given a root
> obligation, close it end-to-end with zero human turns between leaves. Run
> `./recurve --config recurve.toml matrix --gate` and believe the gate.

## Conventions

`missing-surface` claims about `recurvelib.loop.solver`, `reads: none` — each probe drives
`solve`/`close_upward` against a temp on-disk ledger with `SolveContext.sufficiency_check`
swapped for an in-memory fake (a direct ledger write instead of a real Lean build) — the
same swap-the-verifier seam `core/probe.py:ProbeRunner` already gives the rest of the loop.
This exercises the real recursion, ordering, and ledger bookkeeping without a Lean
toolchain; the end-to-end Lean path is exercised separately by the Phase 2 acceptance run
against a scratch navier_stokes copy, not by this suite.

## SOLV-1 — CLOSE is tried before DECOMPOSE

When a node's `close_attempt` already knows a direct proof, `solve` closes it that way and
never consults `cut_proposer` at all — the cost order from §2.2 (cheap moves first).
Negative space: a `solve` that tries DECOMPOSE before (or regardless of) a successful CLOSE
must turn the probe RED.

## SOLV-2 — decompose recurses through every leaf and root-completion closes the root

Given a root with no direct close but a `cut_proposer` returning two directly-closeable
leaves, one `solve` call closes the assembly, both leaves, and — via `close_upward` — the
root itself, with no further calls in between. This is the mechanical heart of the Phase 2
acceptance bar ("zero human turns between leaves"), kept as a permanent, fast regression
guard. Negative space: a `solve` that closes the leaves but leaves the root open (root-
completion never fires) must turn the probe RED.

## SOLV-3 — root-completion never fires on a partial child set

`_ready_to_assemble` requires EVERY expected child of a cut — its leaves and its own
assembly id — to be closed, not just whichever ones happen to be in the ledger so far. This
guards a real bug found while building the Phase 2 acceptance run: the first version checked
`ledger.children_of(parent)` directly, which only sees children already armed, so the first
leaf to close made a 2-leaf cut look fully closed after just one leaf and fired a doomed
assembly attempt. Negative space: a readiness check that reports ready when only a strict
subset of the expected children (plus the assembly) are closed must turn the probe RED.

## SOLV-4 — a node with no applicable move becomes a frontier point

When neither `close_attempt` nor `cut_proposer` returns anything for a node, `solve` records
it in `frontier` — it is surfaced, not silently dropped or mistaken for closed. Negative
space: a `solve` that returns an empty frontier for a node with no available move (or raises
instead of reporting it) must turn the probe RED.
