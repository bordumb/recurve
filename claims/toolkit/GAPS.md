# toolkit — the engine's own promises, probed

> **Reader:** anyone deciding whether to trust this toolkit. Every claim
> below is guarded by a probe with a kept counterexample; run
> `./recurve --config recurve.toml matrix --gate` and believe the gate, not
> this prose. Self-hosting is the standing dogfood that catches
> generalization drift.

## Conventions

Engine-conformance claims map onto the closed class enum as: equivalence and
integrity claims → `wire-mismatch` (implementations/bytes must agree),
operational-discipline claims → `staging` (environment/process guards),
enforcement-surface claims → `missing-surface`. Probes here are `reads: none`
because the engine runs from source — there is no built artifact to go stale;
each probe *executes* the behavior it guards (TK-1 is the one true source
grep, and its claim is about source).

## TK-1 — no origin vocabulary ships

The engine, CLI, schemas, templates, and packs carry no vocabulary from the
projects the toolkit was extracted from — recurve reads as if it had no
first customer. Negative space: a fixture module salted with origin words
must turn the scan RED.

## TK-2 — live-equivalent to both ancestor instances

Re-hosted on the engine, both ancestor instances produce byte-identical
output for every shared command, measured live against the originals (two
documented rendering waivers, where facts are compared instead). Negative
space: an output-corrupting wrapper around the engine must turn the diff RED.

## TK-3 — the outcome map is total

Exit 0 is GREEN, 1 is RED, and anything else — crash, signal, timeout — is
BROKEN, never a verdict; run records and receipts validate structurally.
Negative space: a lenient variant that reads a crash as RED must be caught.

## TK-4 — a second loop is refused

While one loop holds a tree's lock, a second acquire raises instead of
proceeding — two loops on one tree corrupt both. Negative space: a permissive
lock that admits everyone must turn the probe RED.

## TK-5 — unfalsified probes are rejected

`validate` refuses a non-waived probe with no trap fixture: a probe that has
never been seen RED is not yet evidence. Negative space: with enforcement
switched off, the same trap-less guard passes — and the probe goes RED.

## TK-6 — the evidence chain is tamper-evident

A receipt edited after the fact fails validation loudly (the self-hash no
longer matches its canonical content). Negative space: a validator stub that
trusts whatever it reads must turn the probe RED.

## TK-7 — triage deals parallel lanes from disjoint suites

`next --lanes N` (with `--json` for orchestrators) deals up to N lanes:
each suite's highest-value workable open gap, suites pairwise disjoint, so
two lanes can never sculpt the same ledger or prose — the scheduler
guarantees it, not the agents. Parked gaps are excluded like any other
triage. Negative space (guarded by the trap): a lanes answer placing two
lanes in one suite is rejected by the same disjointness check.

## TK-8 — an orchestrator can hold the tree lock across commands

`lock acquire` and `lock release` join `status`/`steal`: the lock file
outlives the acquiring process, so a shell orchestrator spanning many CLI
invocations is still the single loop on the tree — a second `acquire` is
refused with the holder named, and `release` is the run's clean handoff
(`steal` remains the human-only eviction of a dead holder). Negative space
(guarded by the trap): a permissive CLI that grants every acquire turns the
probe RED.

## TK-9 — parallel lanes land through one gated serialization point

`workflows/burndown-parallel.sh` (stamped by `init`) implements the v2
contract (plan §15.9, decided): lanes sculpt in **worktree-isolated** clones
of a git tree, over disjoint suites dealt by `next --lanes`; the **gate is
the serialization point** — candidates land on the real tree one at a time,
each landing requiring the gap's probe GREEN *and* a green fleet gate before
its promotion and per-landing commit; a failing candidate is reverted and
discarded (its gap returns to the backlog for a fresh attempt against the
new baseline), never merged. Promotion belongs to the orchestrator, never to
a lane. Watchdogs: round cap; two consecutive landing-less rounds halt the
run. Negative space (guarded by the trap): a gateless lander that corrupts a
guarded tree is caught by the post-landing fleet-gate invariant.

