# Epic A — Benchmark as a first-class port (kill the SWE-bench fork)

**Leverage:** highest. This is the scale answer. Everything else is cleanup.
**Depends on:** nothing. **Blocks:** Epic B (CLI dispatch needs the registry).

---

## So what? (plain English)

Right now, adding a second benchmark meant photocopying the entire assembly line
and changing one station on it. SWE-bench (`evallib/swebench_pipeline.py`) is a
~385-line copy of the BigCodeBench pipeline where only ~15 lines (how a result is
graded) are actually different. A *third* benchmark would mean a third photocopy.
That doesn't scale, it's a bug farm (fix a row-assembly bug once, it stays broken
in the copies), and it's why the CLI can only run one of the two benchmarks that
already exist.

The cause is precise: the orchestrator makes six things swappable "ports" but
leaves the **seventh — grading — hardwired.** Promote grading to a port, gather
the other four benchmark-specific facts into a small descriptor, and the fork
collapses into one shared pipeline plus a per-benchmark adapter file.

## Current state (evidence)

**The one hardwired step**, in an otherwise all-ports pipeline:

```python
# evallib/orchestrate.py:127-132
oracle = evaluate(task, solution_src, pins[cell["task_id"]],
                  runs=oracle_runs, timeout=oracle_timeout)   # ← BCB-only; not a slot
verdict, flake = oracle["verdict"], oracle["flake_rate"]
```

**The fork it forced.** `evallib/swebench_pipeline.py` re-declares, as
near-verbatim siblings of `orchestrate.py`:
- `REQUIRED_ROW_FIELDS` (`swebench_pipeline.py:183` vs `orchestrate.py:34`)
- `SequencingError` (`:213` vs `:42`), `row_is_complete` (`:209` vs `:47`)
- `_default_gate` (`:237` vs `:52`), `_apply_boundary_port` (`:229` vs `:63`)
- the entire `orchestrate(cell, workspace)` closure: same agent → terminated-guard
  → boundary → done-signal → audit → grade → row-merge sequence, with ~90% of the
  row-assembly dict copy-pasted (`:321-336` vs `:134-149`).

The **only** real differences (the seams a `Benchmark` must carry):

| # | Seam | BigCodeBench | SWE-bench | Evidence |
|---|---|---|---|---|
| 1 | task fields + normalization | `TASK_FIELDS` (3 fields) | `INSTANCE_FIELDS` (10) + `_normalized` (FAIL/PASS_TO_PASS str→list) | `taskstore.py:19`, `swebench_taskstore.py:30,46` |
| 2 | workspace materialization | empty `solution.py`, git init | container checkout + `run_tests.sh` + `container.json` | `materialize.py:46`, `swebench_workspace.py:160` |
| 3 | **grading** | `solution+test → unittest oracle_case` | `git diff → grade_fresh` in a fresh container | `quarantine.py:99`, `swebench_quarantine.py:53` |
| 4 | oracle-env shape | one shared digest for the run | one image **per instance** | `oracle_env.py:88`, `swebench_env.py:59` |
| 5 | calibration keying | per `oracle_env_hash` | per `environment_image_hash` | `calibration.py`, `swebench_calibration.py:30` |

Note seams 1, 2, 4, 5 are already *cleanly separated* in their own modules and
several are reused unchanged (`swebench_calibration.py:25` re-exports
`derive_calibration`; `swebench_warm.py:24` imports `WarmOracle`). **Only seam 3
(grading) lacks a slot in the shared orchestrator.** That is the whole fix.

## Target design

Two pieces: a **grade port** (mechanical, unblocks everything) and a **`Benchmark`
descriptor** (the thin bundle the CLI dispatches on).

### 1. A grade port — the seventh slot

`make_orchestrator` takes a `grade` callable instead of calling `evaluate`
directly. The callable is `grade(cell, task, workspace) -> {verdict, extra_row}`:

```python
# core/orchestrate.py  (target)
def make_orchestrator(agent, tasks_by_id, provenance, *, grade,
                      done/boundary/audit ports unchanged):
    def orchestrate(cell, workspace):
        ... agent, boundary, done_signal, audit ...   # UNCHANGED
        graded = grade(cell, tasks_by_id[cell["task_id"]], workspace)
        row = { ...shared fields..., "oracle_verdict": graded["verdict"],
                **graded.get("extra_row", {}) }       # per-benchmark extras (diff, agreement, per-instance oracle_env_hash)
        return row
    return orchestrate
```

BigCodeBench's grade adapter wraps `quarantine.evaluate` (+ `oracle_env_hash`
from provenance). SWE-bench's wraps `swebench_quarantine.grade_fresh` (+ diff
extraction + per-instance `environment_image_hash`). `swebench_pipeline.py`'s
custom orchestrator **is deleted** — both benchmarks use the one in `core/`.

### 2. A `Benchmark` descriptor — bundle the five seams

A small record (a dataclass/protocol; NOT a heavy framework) that groups the five
seams so the CLI has one thing to look up by name:

```python
# core/benchmark.py  (target)
@dataclass(frozen=True)
class Benchmark:
    name: str                                   # matches manifest [tasks].benchmark
    load_tasks: Callable[[dict, Path], list[dict]]      # seam 1  (load_pinned / fetch_*)
    task_id_key: str                             # "task_id" | "instance_id"
    workspace_port: str                          # seam 2  ("bare"/"recurve_init" | "swe_bench_repo")
    grade: Callable                              # seam 3  (the grade port adapter)
    resolve_oracle_env: Callable[[dict], OracleEnv]     # seam 4  (shared digest | per-instance locks)
    calibrate: Callable                          # seam 5

BENCHMARKS = {}                                  # name -> Benchmark
def register(b): BENCHMARKS[b.name] = b
def resolve(name): ...                           # KeyError-with-known-names, same posture as arm_spec
```

`benchmarks/bigcodebench.py` and `benchmarks/swebench.py` each construct one
`Benchmark` from the existing (already-separated) seam modules and `register()` it.
This is the same registry pattern the codebase already uses six times
(`WORKSPACE_PORTS`, `DONE_SIGNAL_PORTS`, `ADVERSARY_ADAPTERS`, …) — apply it to
the seventh axis.

## Tasks

Each task is independently reviewable and keeps the gated eval claims green
(`.recurve/claims/eval`). Task IDs (A1–A6) are stable identifiers — other epics
cite specific ones (`epic-b-unified-cli.md`, `epic-c-system-under-test.md` both
reference "A4" as the fork deletion) — but the **execution order below is not
numeric**: run **A1 → A2 → A6 → A3 → A4 → A5**.

A6 moved up deliberately. It needs nothing beyond A1/A2 (the grade port +
registry) — it does NOT need SWE-bench's own grading ported (A3) or its fork
deleted (A4) to run. Doing it here means the highest-risk step in this whole
epic — A4, deleting the only working SWE-bench pipeline this repo has, the one
that just ran a real, paid smoke — is *preceded* by independent proof that the
abstraction actually generalizes to a benchmark with nothing at stake, instead
of discovering a gap in the abstraction only after the working fork is gone.

**Build location: `eval/src/`, not `evallib/` in place.** A1–A6 (and the
bonus tasks) are being built as a fresh, parallel implementation under
`eval/src/` (`core/orchestrate.py`, `core/benchmark.py`,
`benchmarks/{bigcodebench,swebench,humaneval_plus}.py`) that imports the
existing, stable `evallib` adapters (arms/audit/done_signal/quarantine/
swebench_*) but never edits a single `evallib` file. This makes A4's own
risk ("the eval is dogfooded, land as separate gated cycles") moot for as
long as the parallel build lasts: `evallib`'s real pipeline — the one that
already ran a real, paid smoke and is what production actually runs — stays
completely untouched and provably working throughout, right up until an
explicit decision to cut over. Validate with
`eval/src/compare_sw6_smoke.py`: it re-runs GRADING ONLY (zero new API
spend) against the real, still-on-disk workspaces from the committed
`eval/runs/sw6-smoke/results.jsonl`, and diffs the new grade port's verdict
against each row's real, recorded one.

- [ ] **A1 — Extract a grade port.** Change `make_orchestrator`
  (`orchestrate.py:83`) to accept a `grade` callable and call it instead of
  `evaluate`. Provide `benchmarks/bigcodebench.py::grade_bcb` wrapping
  `quarantine.evaluate`. *Acceptance:* existing BigCodeBench tests pass byte-for-byte
  (the row is identical); no other benchmark exists yet.

- [ ] **A2 — Define the `Benchmark` descriptor + registry** (`core/benchmark.py`).
  Register BigCodeBench built from the existing seam functions. *Acceptance:*
  `resolve("bigcodebench-hard")` returns a descriptor whose `grade`/`load_tasks`/
  `resolve_oracle_env` reproduce today's behavior.

- [ ] **A6 — Prove the abstraction with a throwaway third benchmark. Do this
  BEFORE A3/A4** (moved up from its original numeric position — see the note
  above; the ID is unchanged so other docs' references to A1–A5 stay valid).
  Add a trivial `benchmarks/humaneval_plus.py` (or a stub) as one file that
  `register()`s and runs end-to-end through the shared pipeline with mocks.
  *Acceptance:* adding a benchmark touches **only** one new file under
  `benchmarks/` + one registry line — the property the design always claimed
  but never had, proven while SWE-bench's own working fork is still there as a
  fallback. Delete the stub after the test proves it, or keep it if HumanEval+
  is on the roadmap (`eval-full.md:87`).

- [ ] **A3 — Move SWE-bench grading behind the grade port.** Wrap
  `swebench_quarantine.grade_fresh` + `extract_diff` + the per-instance
  `environment_image_hash` as `benchmarks/swebench.py::grade_swe` returning
  `{verdict, extra_row: {diff, oracle_agreement, oracle_env_hash}}`. *Acceptance:*
  a mocked SWE cell driven through the **shared** `make_orchestrator` produces a
  row byte-identical to today's `make_swebench_orchestrator` output — AND
  (stronger than a mock) byte-identical to the real rows in the committed
  `eval/runs/sw6-smoke/results.jsonl` when replayed against the same inputs; see
  "Validate against the real smoke, not just mocks" below.

- [ ] **A4 — Delete the fork.** Only once A3 and A6 are both proven. Remove
  `make_swebench_orchestrator` and `make_swebench_pipeline_adapter` from
  `swebench_pipeline.py`; SWE-bench now runs through `core/run_pipeline.py` +
  the shared orchestrator, parameterized by the `swebench` descriptor. Keep the
  genuinely-SWE-only helpers (`extract_diff`, governor wiring
  `configure_governor`/`make_governed_gate_fn`) — move them into
  `benchmarks/swebench.py`. *Acceptance:* `swebench_pipeline.py` no longer defines
  `REQUIRED_ROW_FIELDS`, `_apply_boundary_port`, `_default_gate`,
  `SequencingError`, or a second `orchestrate` closure. Line count drops ~60%.

- [ ] **A5 — Fold the descriptor into the CLI dispatch** (hand-off to Epic B —
  do A1, A2, A6, A3, A4 first, in that order).

### Prelaunch bonus tasks (unlocked by "violent refactors are fine")

With no back-compat burden, don't stop at deleting the *orchestrator* fork —
gut the rest of the duplication and lock the abstraction so it can't rot back.

- [ ] **A7 — Collapse the duplicated SWE-bench modules.** The 9 `swebench_*`
  files are ~15–80% duplication of generic ones. After A1–A4, fold the genuinely-
  unique code into ~2 files (`benchmarks/swebench.py` = the descriptor + grading +
  per-instance env; keep at most one helper module) and **delete** the rest:
  `swebench_taskstore.py` (its `load_jsonl`/`content_hash`/`load_pinned` are
  near-identical to `taskstore.py` — parameterize `TASK_FIELDS`/`_normalized`
  instead), `swebench_env.py`'s duplicated identity-hash (share `oracle_env.py`'s),
  `swebench_calibration.py` (already just re-exports — inline it),
  `swebench_warm.py` (fold `PerInstanceWarmRegistry` into `warm_oracle.py`).
  *Acceptance:* `ls evallib/benchmarks/` shows ~2 SWE files, not 9; every deleted
  module's unique logic has a test proving it survived the move.

- [ ] **A8 — Rename the mislabeled `quarantine.py`.** It presents as generic but is
  BigCodeBench grading (`oracle_case` concat + `task_func`, `quarantine.py:50-84`).
  Move that grading into `benchmarks/bigcodebench.py`; keep only the truly-generic
  bits (pin check, majority-vote loop, `set_grader`) in a `core/` module under an
  honest name (e.g. `core/oracle_runner.py`). *Acceptance:* no "generic" module
  contains a benchmark-specific grading convention.

- [ ] **A9 — A benchmark conformance test — the thing that keeps the abstraction
  honest.** One parametrized test every registered `Benchmark` must pass: loads its
  pinned tasks, materializes a quarantined workspace (hidden oracle absent),
  grades a known-correct artifact → `pass` and a known-wrong one → `fail`, and
  refuses a tampered oracle. *Acceptance:* adding benchmark #3 that doesn't satisfy
  the contract fails this test loudly — so the "one file + one line" property is
  *enforced*, not just documented. This is the highest-value single addition in
  the whole backlog: it's what makes A permanent instead of a snapshot.

## Risks & constraints

- **Keep provenance identical.** The row's `oracle_env_hash` means "shared digest"
  for BCB and "per-instance image hash" for SWE. Carry that difference in the
  grade adapter's `extra_row`, not in the shared orchestrator — do not average the
  two semantics into one. Downstream (Epic F) must know which it is.
- **Don't break the calibration gate.** The spend gate (`calibration.py`,
  `cli.py:93`) must still refuse before any paid cell. `Benchmark.calibrate` and
  `resolve_oracle_env` must preserve the "refuse on drift / refuse uncalibrated"
  posture for both shapes.
- **The eval is dogfooded** — its own `.recurve/claims/eval` gate must stay green
  through every task. Land A1–A4 as separate gated cycles, not one big commit.
- **This is faithful to the design, not a rebellion against it.** The docs said
  "not a fork of the harness" (`eval-swebench-infra.md:171`). The fork happened
  anyway because grading wasn't a port. This epic *delivers* the doc's stated
  intent; cite it in the PR.
- **Validate against the real smoke, not just mocks — this review's own blind
  spot showed up in practice.** This diagnosis was written from a static code
  read, and it's accurate — but two real, structural bugs in exactly the code
  this epic touches were found only by actually *running* the SWE-bench
  pipeline for real, and neither would have surfaced from reading the source:
  (1) the governor's `build_cycle_snapshot(tree, "HEAD", ...)` requires a
  clean, committed tree, but the pre-existing pipeline never committed the
  agent's work — every single governed cell failed the same way, independent
  of the task, and only running one revealed it; (2) the isolated review
  snapshot (`git archive`, by design no `.git`) makes a git-diff-based
  reviewer script silently, vacuously pass everything — confirmed only by
  actually invoking a real review and seeing `STOP-SUCCESS` come back
  hollow. Both are fixed (`.recurve/claims/swebench` SW-8/SW-9,
  `swebench_pipeline.py`/`swebench_governor_reviewer.py`), and the real
  results are committed at `eval/runs/sw6-smoke/results.jsonl`. When A3/A4
  claim "byte-identical row", diff against *that* file too, not only a mocked
  fixture — a mock can't reproduce a bug that only exists in what a live
  process actually does.
