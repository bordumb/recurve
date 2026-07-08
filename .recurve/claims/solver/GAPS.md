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
toolchain; the end-to-end Lean path (Phase 2's close/decompose/root-completion, Phase 3's
DISCOVER against the real `dyadic_lyapunov` fansearch domain) is exercised separately by
the acceptance runs against a scratch navier_stokes copy, not by this suite.

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

## SOLV-5 — budget exhaustion halts an unbounded recursion

`solve` checks `ctx.budget.exhausted()` before spending effort on each obligation; an
always-decomposable chain that would otherwise recurse forever stops at the budget's move
cap, with the node it stopped on surfaced as frontier. This is the "spends within budget
rather than spinning" guarantee (§2.3, §2.7) — a misdirected or genuinely unbounded search
costs at most the configured budget, never an unbounded run. Negative space: a budget that
never reports itself exhausted (or a `solve` that doesn't check it) must turn the probe RED.

## SOLV-6 — a genuine frontier node is parked with its reason

When `ctx.parked_root` is set, a node `solve` surfaces to the frontier is written to
`loop/parked.py:ParkedStore` with the reason it couldn't move forward — the durable,
reconstructable record of exactly where the known part of a problem ends (§2.3, §2.7).
Negative space: a `solve` that reports a node in its in-memory `frontier` result but never
persists it to the parked store must turn the probe RED.

## SOLV-7 — a refuted node is restated, not attempted under its original framing

When `ctx.refute_attempt` finds a node's current framing is known-false or ill-posed, `solve`
does not try to CLOSE or DECOMPOSE it as originally stated — `ctx.restate_attempt` supplies a
corrected framing to recurse into instead (§2.1's `restate_or_abandon`; the historical example
is the SUB-HEAT-SG → -FWD naming fix). Negative space: a `solve` that ignores
`refute_attempt`/`restate_attempt` and tries the node's original statement directly must turn
the probe RED.

## SOLV-8 — DISCOVER closes on a gate-confirmed candidate, surfaces frontier on a dry search

At a node with `ctx.discover_attempt` registered, a `True` outcome (a candidate search found
and promoted a gate-confirmed witness) closes the node without ever consulting
`cut_proposer`; a `False` outcome (the search came up dry) surfaces the node to the frontier
directly — DISCOVER is terminal for that node, never silently retried as a decomposition
(§2.4). Negative space: a `solve` that ignores `discover_attempt` (or falls through to
DECOMPOSE after a dry search) must turn the probe RED.
