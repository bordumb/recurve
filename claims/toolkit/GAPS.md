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


## TK-10 — the unarmed backlog is visible to orchestrators

`next --json` reports, beside the strict-ledger triage, a `drafts` list
(per-suite pending counts from `gaps.draft.yaml`) and an
`adjudications_pending` count (unresolved `DECIDED: (pending` forks in
ADJUDICATE.md). An empty `recommended` therefore has two distinguishable
readings — "the spec is burned down" versus "the next wave is unarmed" —
and a loop can act on the difference. The human rendering prints the same
backlog hint. Negative space (guarded by the trap): a triage output without
these fields reads as done while most of the spec sits unprobed.

## TK-11 — record append is idempotent

One cycle's record lands in `records.jsonl` exactly once, however many
times it is appended: RUN.md tells the agent to append, burndown.sh appends
the same result file on the agent's behalf, and the journal must not
double-count the cycle. `record append` skips a record whose canonical
serialization already exists in the journal. Negative space (guarded by the
trap): a blind appender writes two lines and every downstream consumer
(triage priors, cost prediction) counts each cycle twice.

## TK-12 — the burndown loops arm the next wave

The serial loop (`workflows/burndown.sh`) no longer halts at "no work left"
while drafts pend: an arming stage sends one agent to author probes + traps
for the next draft batch (never product code), runs the `baseline` ceremony
for real, and continues sculpting — bounded by `ARM_WAVES`/`WAVE`, refusing
to arm while ADJUDICATE.md holds a pending fork (a probe encodes a decision,
never a guess), and halting loudly when an arming opens no work. The
parallel and orchestrator twins surface the unarmed backlog at halt instead
of reporting plain "no work left". Negative space (guarded by the trap): the
pre-wave template strands the bulk of a spec in `gaps.draft.yaml` after the
first wave closes.

## TK-13 — report renders the deterministic run dataset

`report` turns what the loop already wrote down into one reviewable page,
deterministically — no narrator, no network: progress (closed/open/parked
counts by suite, class, and severity, plus the remaining workable count),
per-cycle durations with mean/median and the last-5 trend, an ETA projection
from the last closed cycles (optimistic/pessimistic bounds, assumptions
stated, "insufficient data" under two closed cycles), and — when the target
tree is a git repo — a diff analysis over the range the records cover:
lines added/removed, files touched, top directories, an honesty scan
counting ADDED lines that match the configured suppression patterns, and a
"review before signing" list for the largest diffs touching `[report]
sensitive_paths`. Negative space (guarded by the traps): a report that
omits the honesty section, or counts zero on a seeded TODO addition, reads
complete while a suppressed check sails through.

## TK-14 — --narrate appends prose without ever owning the report

`report --narrate` pipes the rendered report plus a JSON array of the cycle
records to the `[report] narrator` command from recurve.toml and appends
its stdout under `## Narrative`. Without a configured narrator the flag is
a clean one-line usage error (exit 2); without the flag the deterministic
report renders as always. A narrator that fails or times out costs only
the prose: the deterministic report still prints (or appends) and the exit
is 1 — narration may editorialize over the numbers, never replace them.
Negative space (guarded by the trap): an engine that prints only what the
narrator returns loses the entire report to a quiet narrator.

## TK-15 — the stamped burndown workflow is sandbox-clean and root-absolute

The `burndown.js` that `init` stamps into a target carries no
sandbox-forbidden runtime call — no `Date.now()`, `Math.random()`, or
`new Date()` (the orchestrator sandbox rejects wall-clock and RNG because
they break resume) — and resolves every path it hands an agent from an
absolute `const ROOT = '/...'`, stamped in at init time: the cycle prompt
reads `${ROOT}/.recurve/RUN.md` and writes
`${ROOT}/.recurve/state/reports/...`, never a cwd-relative `.recurve/RUN.md`
that breaks when the orchestrator launches from another directory. The probe
asserts against a FRESHLY STAMPED file, so a template that mis-interpolates
at stamp time is caught too. Negative space (guarded by the trap): a
regressed workflow that reintroduces a wall-clock `Date.now()` RUN_ID or a
bare-relative `.recurve/RUN.md` read turns the probe RED.

## TK-16 — matrix --gate federates each sculpt's own gate command

A config may declare secondary trees as `[sculpts.<name>]` tables (FR-C); the
PRIMARY tree is `[target]`. `recurve matrix --gate` FEDERATES across them: it
is green only when the target's probes AND every declared sculpt's own `gate`
command (run in that sculpt's tree dir) pass. A sculpt whose gate exits
non-zero turns the federated gate RED even when the target probe is GREEN; one
line per sculpt is printed (`sculpt <name>: gate OK/FAILED (exit N)`). A
single-tree config — no `[sculpts.*]` — has no sculpt iterations, so it gates
exactly as it did before. Negative space (guarded by the trap): an engine that
reports the federated gate GREEN while a sculpt's gate fails has not federated
at all, and the probe turns RED.
