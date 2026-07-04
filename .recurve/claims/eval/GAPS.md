# eval — the recurve evaluation pipeline, gated

The instrument is held to the standard it measures. The `eval/` pipeline
(docs/plans/eval-poc.md §5) turns an experiment manifest into pinned cells, runs
them through the BYO-agent seam, quarantines a held-out oracle, and analyzes the
results deterministically. Each stage is a claim here.

Design: the pipeline's core logic is stdlib-only, so these probes are hermetic —
they drive the real `evallib` code against fixtures, never the network or a paid
run. The one genuinely external dependency (fetching the real BigCodeBench-Hard
revision from HuggingFace) is an `oracle_waiver`: the probe runs full-strength
where the dataset is reachable and SKIPs (visible, non-blocking debt) where it is
not.

## EV-1 — TaskStore pins the benchmark to a content hash

`taskstore.py` loads a task set and pins it to a deterministic SHA-256 over the
canonical task content; `verify_pin` rejects any dataset that does not match its
recorded pin, and a changed task changes the hash. The pinning logic is
stdlib-only (hermetic); the real BigCodeBench-Hard fetch from HuggingFace needs
the optional `datasets` dependency and is oracle-waived where it is absent.
Negative space (guarded by the trap): a `verify_pin` that accepts a tampered
dataset against its original pin.

## EV-2 — Materializer builds A0/A3 workspaces and quarantines the oracle

`arms.py` maps an arm name to its workspace spec (pure): A0 is the bare task
statement + empty `solution.py`; A3 is the same, `recurve init`-ed.
`materialize.py` builds the git-init'd tmpdir, writing only what the agent may
see — never the hidden `test` field — and `assert_quarantined` refuses any
workspace in which the hidden test text appears. Negative space (guarded by the
trap): a materializer that accepts a workspace containing the hidden oracle.

## EV-3 — Runner: pinned matrix + resumable work queue

`plan.expand` turns a manifest and a pinned task set into the full cross product
(task × arm × model × budget × seed) with cell IDs derived from coordinates,
written to `matrix.jsonl` before any agent runs. `runner.run` drives each cell
through a BYO-agent adapter and seals exactly one row per cell; the resume
invariant is load-bearing — a re-run over a completed matrix invokes the agent
zero times, so a long paid run is safe to stop and restart. The adapters
(`claude.py`, `telemetry.py`) and the three CLI verbs complete the surface; the
gated logic is driven by a mock adapter (no spend). Negative space (guarded by
the trap): a runner that re-invokes the agent on already-sealed cells.

## EV-4 — Quarantine evaluator: isolated oracle, 3× majority, tamper-refused

`quarantine.py` runs the hidden unittest suite against the agent's final
`solution.py` in a separate process (a bigcodebench venv in a real run; a clean
subprocess here), never inside the agent's workspace. `oracle_verdict` runs the
suite N times and returns the majority verdict plus the flake rate; `evaluate`
refuses to grade unless the oracle's test text matches the checksum recorded at
fetch time. Negative space (guarded by the trap): grading a solution with a
tampered oracle against the original pin.

## EV-5 — Analysis: deterministic tables from results.jsonl

`analyze.py` is a pure function of the results: same rows in any order produce
byte-identical output. It computes the §4 metrics — per model × arm
shipped-bad-work rate, FDR, ΔFDR, oracle pass rate — with Wilson 95% intervals
and a paired McNemar within each model, all closed-form in stdlib (no scipy, no
notebook state). Negative space (guarded by the trap): an analysis whose output
depends on input row order (non-deterministic).

## EV-6 — Orchestrator: agent → terminal state → oracle → one analyze row

`orchestrate.py` is what a cell does, in the order it must happen: run the
agent, confirm the agent process **terminated** (`SequencingError` refuses to
quarantine a live workspace), read the final `solution.py`, grade it against the
pinned held-out oracle, and seal a row with `declared_done` + `oracle_verdict` +
per-row provenance (dataset revision, model verbatim, recurve commit, adapter
version, seed). For a recurve-gated arm it also records the `terminal_state`
(gate verdict + why the run ended) and the `gate_outcome` from it. The
gated-vs-bare branch keys on the arm's `recurve` **property** (`arm_spec`), not
its name, so a manifest may name a gated arm anything and it still routes right.
`row_is_complete` refuses a run-only row that would leave `analyze` without its
dependent variable. Negative space (guarded by the traps): a declared-only row
accepted as complete; a live workspace quarantined; a differently-named gated
arm routed to the bare path.

## EV-7 — Gated-run outcome classifier: refusal vs process-failure

`classify.py` separates a genuine gate refusal from a harness-operation failure
— the distinction §4/§8.3 insist on, and it cannot be read from the workspace
alone: a red gate is a *refusal* only if the run ended on budget exhaustion,
which is telemetry run-state, not workspace state. `classify_gated_run(workspace,
terminal_state)` reads both. `has_wellformed_claim` checks for a probe with a
kept trap. Boundaries: no claim → `process_failed`; gate BROKEN → `process_failed`
(a probe that can't decide isn't the gate refusing work); gate green → `declared`;
gate red + budget-exhausted → `gate_refused`; gate red + crashed → `process_failed`.
Negative space (a trap per boundary): a no-claim / broken / crashed run
miscredited to the gate as a refusal.

## EV-8 — Telemetry + token-cap enforcement (budget-matched)

`telemetry.parse_usage` extracts token counts from the agent's JSON;
`cost_usd` prices them from the dated table and RAISES on an unpriced model
(never a silent $0); `wall_clock` captures elapsed. Because `claude -p` has no
hard token cap and `recurve run --cap` bounds cycles not tokens, `budget.py`'s
`run_gated_burndown` accumulates a cell's spend across its many cycles against
ONE `TokenBudget` and stops starting cycles once the cap is reached — reporting
the `stop_reason` (gate_green vs budget_exhausted) that EV-6 records and EV-7
classifies from. The cap is **per cell, not per cycle**: the recorded total is
bounded by cap + one cycle's overshoot, never many multiples of it. The gated
Claude adapter drives the real run through it. Negative space (guarded by the
traps): `cost_usd` silently pricing an unknown model at $0; a per-cycle cap that
lets a cell overshoot without bound.
