# eval/ architecture review — index

**Audience:** an engineer or LLM with *zero prior context* on this codebase.
Every claim below cites a real file and line. Read this page first, then open the
epic file for whatever you're assigned.

**Scope of the review:** `recurve/eval/` — the pipeline that measures whether
recurve reduces "shipped-bad-work." The review answers four questions the tech
lead asked: (1) are configurations dynamic enough? (2) is the eval filesystem as
good as it can be? (3) is the code extensible for N benchmarks? (4) is too much
of recurve hardcoded into `eval/`?

**This review is a static code read — it has a real blind spot.** Running the
real SWE-bench pipeline for the first time (after this review was written)
surfaced two structural bugs in exactly the code Epic A touches, neither
visible from source alone: the governor's snapshot mechanism silently failed
on every real cell (`.recurve/claims/swebench` SW-8), and its reviewer script
was silently reviewing nothing at all (SW-9) — both only observable by
actually invoking the pipeline. See Epic A's "Validate against the real
smoke, not just mocks" for the details; the real run's evidence is committed
at `eval/runs/sw6-smoke/results.jsonl`. Whoever picks up Epic A: diff against
that file, not only mocks.

---

## TL;DR verdict (brutally honest)

**The kernel is genuinely well-built. The extensibility model is half-finished.**

`eval/` was designed with a clean hexagonal ("ports and adapters") core: an *arm*
is a tuple of port selections (`evallib/arms.py`), and the cell orchestrator
(`evallib/orchestrate.py`) is a fixed pipeline that fills those ports by name and
never branches on which arm is running. The provenance discipline — pin
everything that can change a verdict, refuse on drift, gate all spend behind a
calibration — is excellent and rare (`evallib/calibration.py`,
`evallib/taskstore.py`). **Do not rewrite these.**

But extensibility was only ever designed along **one axis: arms**. The other
three axes that a real multi-benchmark eval program varies —

1. the **benchmark** (BigCodeBench vs SWE-bench vs the next one),
2. the **system under test** (recurve today; a competitor or a newer recurve tomorrow),
3. the **agent runtime** (`claude -p` today; GPT/Gemini/aider tomorrow),

— were each treated as *bespoke, hardcoded* rather than as ports. The bill for
that is already visible in the tree:

- **SWE-bench is a ~9-module parallel fork** (`evallib/swebench_*.py`) that
  copy-pastes a ~110-line orchestrator skeleton to swap one ~15-line grading
  step — and which **the CLI cannot even run** (`evallib/cli.py` has zero
  SWE-bench wiring; the `eval swebench plan`/`eval swebench build` verbs that the
  code's own error messages tell users to run **do not exist**).
- **`recurve matrix --gate` is re-implemented as a raw subprocess in 6 files**
  instead of one adapter.
- The manifest **writes `benchmark = "bigcodebench-hard"` and then ignores it** —
  `_resolve_tasks` always calls `fetch_bigcodebench_hard` (`evallib/cli.py:22-30`).
- The analysis layer **hardcodes the A0-vs-A3 arm pair** (`evallib/analyze.py:69,76`),
  so ablation arms (A4–A10) and SWE-bench's A0/A9 silently get no paired statistics.

Adding benchmark #3 today means forking the module family a second time and
forking the CLI a second time. That is the scale problem in one sentence.

**The fix is not a rewrite — it's finishing the abstraction the kernel already
implies.** The design docs already state the intended rule ("SWE-bench is a new
WorkspacePort/oracle adapter pair, **not a fork of the harness**"); the code
violated it under deadline. This report turns that gap into a backlog.

> **Want the "why" before the "what"?** [00-diagnosis.md](00-diagnosis.md) is the
> full architecture narrative — the single root cause (grading was left hardwired
> while six sibling axes became ports), the deliberate design bet that produced it,
> and how it fans out into all seven epics. Read it after this page.

---

## Prelaunch / solo lens (read this before you touch anything)

This is a **prelaunch personal project** — no external users, no API to keep
stable, one real run on disk (`runs/o6/`, a $2 smoke). That changes the *strategy*
but **not the diagnosis** (the missing-port hole is structural truth at any
stage). Two adjustments follow, and they pull in opposite directions:

**1. Delete, don't deprecate. Sweep, don't tiptoe.** Every "keep backward
compatibility / default the missing key / isolate the pure-move commit / land as
separate cycles" caution in the epics below is **void.** There's nothing to
preserve. Do Epic A + the module reorg (G1) + the `quarantine.py` rename as **one
violent sweep**. Treat `runs/o6/` as a throwaway fixture, not a schema constraint
(better: move it to `tests/fixtures/` or delete it). The big-diff worries assume a
reviewer you don't have.

**2. YAGNI gets *stronger*, not weaker.** Moving fast solo is exactly when
speculative abstraction hurts most — you pay the indirection cost forever and the
second use-case may never come. Several epics propose ports for things that have
**exactly one implementation today**. Build the seam (one adapter, deduped); do
**not** build the registry/protocol until a second implementation actually exists:

| Build now (real payoff, ≥2 cases exist) | Defer (one case today — just leave a clean seam) |
|---|---|
| **A** — Benchmark port. Two benchmarks already exist; the fork is live pain. | **C4** — `SystemUnderTest` *protocol*. One SUT (recurve). Do the dedup (C1–C3), skip the port. |
| **B** — Unified CLI. SWE-bench is literally unrunnable today. | **D** — Agent-runtime *port*. One runtime (`claude -p`). Isolate `claude.py`, skip the registry. |
| **C1–C3** — Collapse the 6 `recurve` gate copies to one adapter. Pure debt. | **E4** — Manifest-declarable arms. `_ARMS` in Python is fine and type-safe solo. |
| **F** — Un-bake A0/A3. The ablation ladder is on the near roadmap. | **G4/G5** — Multi-machine lease / container caps. One machine, smoke-sized runs. |
| **E1–E3** — Schema validation, dataset registry, budget-unit fix. Cheap correctness. | |

The right-hand column isn't "never" — it's "the day a second SUT / runtime /
machine is real, and not one hour before." Note the seam in the code
(`# one impl today; add a registry when a second exists`) and move on.

**The one discipline that does NOT relax:** keep the eval's own dogfooding gate
(`.recurve/claims/eval`) green through the sweep. Moving fast solo means it's your
*only* safety net — that's a reason to guard it, not drop it.

---

## Direct answers to the four questions

### 1. Are configurations dynamic enough? — **No.**
The manifest *looks* declarative but several things it names are ignored or must
be edited in Python:
- `[tasks].benchmark` is written but never dispatched on (`evallib/cli.py:22-30`).
- Arms live in a Python dict `_ARMS` (`evallib/arms.py:77-109`); a new arm is a
  code change, not config.
- Dataset pins (`hash`/`count`/`revision`) are copy-pasted into every experiment
  TOML (`experiments/o6-smoke.toml`, `poc-bcb-hard.toml` — identical BCB pin
  block); there is no shared dataset lock.
- `[oracle.env]` assumes a single shared docker digest; SWE-bench needs
  `per_instance = true` handled by entirely different code (`experiments/sw6-smoke.toml:46-51`).
- **Budget-unit drift:** the live manifest uses dollars (`budgets = [0.50]`,
  `poc-bcb-hard.toml:8`) but a frozen run on disk uses tokens
  (`budgets = [60000]`, `runs/o6/manifest.toml:12`). Same key, two units, no
  `budget_unit` field to disambiguate. → **Epic E**.

### 2. Is the eval filesystem as good as it can be? — **Half.**
The **run layout is genuinely good and should be kept**: each verb writes a file
the next verb reads (`manifest.toml` → `matrix.jsonl` → `results.jsonl` →
`analysis/`), so every phase boundary is an inspectable, diffable artifact
(`eval/README.md:46-52`), and `.gitignore` commits the evidence while excluding
the heavy reproducible workspaces (`eval/.gitignore`). Weaknesses: the module
directory `evallib/` is flat with ~20 generic modules interleaved with ~9
`swebench_*` ones (no `core/` vs `benchmarks/` vs `adapters/` separation); each
cell workspace is a full tree with its own `.git`/`.recurve`/`__pycache__` and no
GC; and the runner is a single-process `ThreadPoolExecutor` with no sharding.
→ **Epic G**.

### 3. Is the code easily extensible for N benchmarks? — **No.**
There is no `Benchmark` abstraction. BigCodeBench is hardwired into the CLI and
the grading substrate; SWE-bench is a parallel fork the CLI can't reach. The four
things that *actually* differ between benchmarks (task loading, workspace
materialization, grading, shared-vs-per-instance oracle env) are real seams — but
they're spread across duplicated modules instead of collected behind one
protocol. → **Epics A and B**.

### 4. Is too much of recurve hardcoded into `eval/`? — **Yes, but nuance matters.**
Two different things are tangled here:
- **Accidental duplication (pure debt):** `recurve matrix --gate` appears as a raw
  subprocess in `evallib/done_signal.py:30`, `orchestrate.py:58`,
  `swebench_pipeline.py:238`, `adapters/claude.py:116` (and referenced in
  `run_pipeline.py`, `arms.py`). Six sites, one command. Collapse to one adapter. → **Epic C**.
- **Legitimate coupling (by design, but should be a port):** `eval/`'s *purpose*
  is to measure recurve, so knowing about `recurve init` / the gate / `recurve
  decide` / probes+traps is not wrong. But it should live behind a single
  `SystemUnderTest` port so a newer recurve, or a comparison against a competitor,
  doesn't require kernel surgery. `classify.py` (reads recurve's `probes/*.sh` +
  `.trap` layout) and `adapters/claude.py` (hardwires `claude -p`) are the other
  coupling hotspots. → **Epics C and D**.

Note the one benchmark-coupling that is *not* recurve: `evallib/quarantine.py`
bakes in BigCodeBench's "concatenate solution+test into one `oracle_case` module,
call `task_func`" grading convention (`quarantine.py:50-84`). That belongs to the
benchmark, not the kernel. → **Epic A**.

---

## What is genuinely good — do NOT refactor these

If you're handed an epic, protect these while you work. They are the reason the
eval is trustworthy, and a careless refactor will destroy that.

| Asset | Where | Why it's good |
|---|---|---|
| The arm ports/adapters kernel | `evallib/arms.py`, `orchestrate.py`, `materialize.py`, `done_signal.py` | A fixed pipeline with named slots; adding an arm never edits the orchestrator. This is the pattern the benchmark axis should copy, not replace. |
| Pin-and-refuse provenance | `taskstore.py`, `oracle_env.py`, `oracle_docker.py` | Every verdict-affecting input is content-hashed and refused on drift. Keep this invariant in any new benchmark adapter. |
| The calibration spend-gate | `calibration.py`, `cli.py:93-108` | No paid cell runs unless canonical solutions pass through the *finished* oracle path, keyed by `(oracle_env_hash, dataset_hash)`. This is the structural defense against a harness that flatters itself. Any `Benchmark` protocol must preserve it. |
| Crash-resilient resumable runner | `runner.py` | Seals each row with `fsync` the moment a cell finishes; resumes by skipping sealed cell ids. Reuse it for every benchmark — do not fork it. |
| Deterministic, order-invariant analysis | `analyze.py`, `render.py` | Tables and figures are a pure function of `results.jsonl`; no notebook state. (The only fix here is un-baking the A0/A3 pair — Epic F — not the determinism.) |
| Reused primitives across benchmarks | `swebench_calibration.py:25-27` (re-exports `derive_calibration` unchanged), `swebench_warm.py:24` (imports `WarmOracle` unchanged) | Proof the abstraction *can* be shared — these did it right. The pipeline layer just didn't follow suit. |

---

## The epics

Each epic is a separate file in this directory. They are ordered by leverage:
A and B unlock N-benchmark scale; C–G are independent cleanups you can parallelize.

| # | Epic | The problem in one line | Depends on |
|---|---|---|---|
| **A** | [Benchmark as a first-class port](epic-a-benchmark-port.md) | SWE-bench is a copy-paste fork of the orchestrator; there's no `Benchmark` protocol. | — |
| **B** | [One CLI for N benchmarks](epic-b-unified-cli.md) | `cli.py` is BigCodeBench-only; SWE-bench has no runnable verb. | A |
| **C** | [Decouple the system under test (recurve)](epic-c-system-under-test.md) | `recurve matrix --gate` is duplicated across 6 files; no `SystemUnderTest` port. | — |
| **D** | [Agent runtime as a port](epic-d-agent-runtime.md) | `claude -p` is hardwired; no way to eval a different agent CLI. | — |
| **E** | [A manifest that declares, not assumes](epic-e-config-schema.md) | `benchmark` ignored, arms in Python, dataset pins duplicated, budget-unit drift. | A (for benchmark dispatch) |
| **F** | [Analysis generality](epic-f-analysis-generality.md) | `analyze.py` hardcodes the A0-vs-A3 comparison. | — |
| **G** | [Scale & filesystem](epic-g-scale-filesystem.md) | Flat module dir, per-cell heavy workspaces, single-process runner. | A (module reorg is cleaner after A) |

**Suggested sequencing:** A → B first (they are the actual scale answer and E/G
partly depend on A's registry). C, D, F can proceed in parallel by separate
owners immediately. G's module reorg is easiest to land right after A.

---

## Glossary (for zero-context readers)

- **cell** — one experiment data point: a `(task, arm, model, budget, seed)`
  tuple. The unit of work the runner drives (`evallib/plan.py:35`).
- **arm** — an experimental condition, expressed as a tuple of *port* selections
  (workspace, done-signal, boundary, audit, adversary, governor). `A0` = "0%
  recurve" (bare workspace, agent self-reports done); `A3` = "100% recurve"
  (recurve-init workspace, the gate decides done). See `evallib/arms.py`.
- **port** — a named extension point with a small set of interchangeable adapters
  (e.g. `WorkspacePort ∈ {bare, recurve_init, swe_bench_repo}`). The kernel calls
  a port by name and never hardcodes a branch.
- **oracle** — the held-out grader (hidden tests for BigCodeBench; a diff applied
  in a fresh container for SWE-bench). Never shown to the agent
  (`materialize.assert_quarantined`).
- **calibration** — grading the *canonical* (known-correct) solutions through the
  finished oracle path. If they don't pass, the harness is broken, and no paid run
  is allowed (`evallib/calibration.py`).
- **system under test (SUT)** — the thing the eval is measuring: **recurve**. Not
  to be confused with the **agent runtime** (`claude -p`), which is the model
  process doing the task, or the **harness** (`eval`), which is this pipeline.
- **the gate** — `recurve matrix --gate`; exit 0 = green (claims pass), 1 = red.
  The SUT's own verdict that a task is genuinely done.
