# The diagnosis: one missing abstraction axis

> Read [README.md](README.md) first for the verdict and the four answers. This
> file is the "why" behind all seven epics — the single root cause they fan out
> from. It is the brutally-honest architecture narrative.

## The thesis

`eval/` has a **beautiful kernel with one hole in it.** The kernel treats an
experiment as a matrix of *cells*, and it makes everything that varies *between
arms* a **named port**: workspace, done-signal, boundary, audit, adversary,
governor — six axes, each a string that indexes into a registry
(`evallib/orchestrate.py:9-20`, `evallib/arms.py:37-64`). The orchestrator is a
fixed pipeline that fills those slots by name and *never branches on which arm is
running*. This is textbook hexagonal architecture and it is done well.

The hole: **there is a seventh thing that varies — not between arms, but between
*benchmarks* — and it was left hardwired instead of made a port.** That thing is
**grading** (the oracle). In `make_orchestrator`, grading is a direct call:

```python
# evallib/orchestrate.py:127-132  — the one hardwired step in an otherwise all-ports pipeline
oracle = evaluate(task, solution_src, pins[cell["task_id"]],
                  runs=oracle_runs, timeout=oracle_timeout)
verdict, flake = oracle["verdict"], oracle["flake_rate"]
```

`evaluate` (`evallib/quarantine.py:99`) is BigCodeBench-shaped to the bone: it
concatenates `solution.py` + the hidden test into one `oracle_case` module and
runs `python -m unittest`, because "BigCodeBench concatenates the solution and
the test into ONE module … exactly as the benchmark intends"
(`quarantine.py:50-84`). A SWE-bench cell can't be graded that way — its artifact
is a *git diff* applied in a *fresh container*. So when SWE-bench arrived, the
author could not swap the grade step (it isn't a slot), and the "no kernel
surgery" rule forbade branching the orchestrator. The only move left was to
**copy the entire orchestrator** and change the one line. That copy is
`evallib/swebench_pipeline.py`.

**Every problem in this review is a shadow of that one hole.**

## The bet the design made — and exactly where it broke

This was not an oversight; it was a *deliberate architectural bet*, and the
design docs state it plainly:

> "Short answer to 'do we need new ports/adapters architecture?': **no — the seam
> already exists.**" — `docs/plans/eval-full.md:161-165`

The bet: a new benchmark enters as **a new `WorkspacePort` value + a bespoke
oracle path**, never as a first-class type. The rule that followed:

> "SWE-bench is a new `WorkspacePort`/oracle adapter pair, **not a fork of the
> harness.**" — `docs/plans/eval-swebench-infra.md:171-173`

> "adding a WorkspacePort value never touches the kernel pipeline" —
> `docs/plans/eval-arm-kernel.md:43-47`

Here is the precise failure. The bet **held for the workspace**: `swe_bench_repo`
really is one new port value plus one registry line
(`evallib/materialize.py:85-89`) — exactly as promised. The bet **broke for
grading**, because grading was never given the same treatment as the workspace.
The workspace is a port; the oracle is a hardwired function call. So the
"adapter pair" the doc imagined turned out to be one adapter (workspace, clean)
and one *impossible* adapter (oracle, no slot to plug into) — and the impossible
half took the whole pipeline down with it into a fork.

The design docs even sensed the danger without closing it:
`eval-swebench-infra.md:15-36` ("Why this isn't just 'point BigCodeBench's
harness at a new benchmark'") correctly lists the real differences — the task is
a repo, one oracle image per repo/version, grading a working environment. Those
differences are **real and legitimate**. But they are exactly 4–5 named seams;
they never justified duplicating the boundary/done-signal/audit/row-assembly
skeleton that has *nothing* to do with those differences.

## The evidence: what got duplicated vs what's genuinely different

An independent read of both pipelines (folded into [Epic A](epic-a-benchmark-port.md))
found: the SWE-bench module **re-implements** `_apply_boundary_port`,
`_default_gate`, `SequencingError`, `REQUIRED_ROW_FIELDS`, `row_is_complete`, and
~90% of the row-assembly merge — line-for-line siblings of `orchestrate.py`. The
**only** genuinely benchmark-specific seams are:

| Seam | BigCodeBench | SWE-bench | Where |
|---|---|---|---|
| task fields | `TASK_FIELDS` (3) | `INSTANCE_FIELDS` (10) + `_normalized` | `taskstore.py:19` / `swebench_taskstore.py:30,46` |
| workspace | empty `solution.py` | live container checkout | `materialize.py:46` / `swebench_workspace.py:160` |
| **grading** | solution+test → `unittest` | diff → fresh container | `quarantine.py:99` / `swebench_quarantine.py:53` |
| oracle env | one shared digest | one image **per instance** | `oracle_env.py:88` / `swebench_env.py:59` |
| calibration keying | per oracle-env | per instance-env | `calibration.py` / `swebench_calibration.py:30` |

That table **is** the `Benchmark` abstraction. Five fields. Everything else in
`swebench_pipeline.py` is duplication that should not exist.

## The current module map (why the tree looks the way it does)

`evallib/` is flat: ~20 generic modules interleaved with ~9 `swebench_*` ones,
with no signal about which layer a file belongs to.

```
evallib/
  cli.py                 ← entry point — BigCodeBench-ONLY (no swebench verbs)
  plan.py arms.py        ← kernel: cells, arm ports          [KEEP]
  orchestrate.py         ← kernel: the fixed pipeline          [KEEP, add a grade port]
  runner.py              ← kernel: resumable queue             [KEEP]
  materialize.py         ← WorkspacePort registry              [KEEP]
  done_signal.py audit.py boundary(via recurvelib)  ← arm ports [KEEP]
  quarantine.py          ← "generic" but actually BCB grading  ← MISLABELED
  calibration.py oracle_env.py oracle_docker.py warm_oracle.py oracle_build.py  ← oracle infra [KEEP]
  analyze.py render.py   ← analysis — hardcodes A0/A3          [Epic F]
  adapters/claude.py     ← agent runtime — hardwires `claude -p` [Epic D]
  adapters/telemetry.py  ← pricing/usage                       [KEEP]
  swebench_pipeline.py       ← FORK of orchestrate+run_pipeline  ← DELETE after Epic A
  swebench_taskstore.py      ← ~80% dup of taskstore
  swebench_env.py            ← ~65% dup of oracle_env
  swebench_quarantine.py     ← the ONE real seam (grading)      ← becomes a grade adapter
  swebench_workspace.py      ← the ONE clean port (workspace)   ← already right
  swebench_warm.py           ← reuses WarmOracle + per-instance registry
  swebench_calibration.py    ← re-exports calibration unchanged + per-instance keying
  swebench_majority.py swebench_governor_reviewer.py  ← misc
```

The target shape (see [Epic G](epic-g-scale-filesystem.md)):

```
evallib/
  core/        ← plan, arms, orchestrate, runner, calibration, oracle_*, analyze, render
  benchmarks/  ← bigcodebench.py, swebench.py   (each: the 5-field descriptor + its adapters)
  adapters/    ← agent runtimes (claude.py, …), telemetry
  sut/         ← the recurve gate/init/decide adapter (Epic C)
  cli.py       ← dispatches on the benchmark registry
```

## How the hole fans out into the seven epics

| Symptom | Epic |
|---|---|
| Grading isn't a port → SWE-bench forked the pipeline | **A** — promote grading to a port; bundle the 5 seams into a `Benchmark` descriptor |
| CLI is BigCodeBench-only; SWE-bench unrunnable | **B** — dispatch the CLI on the benchmark registry |
| `recurve matrix --gate` duplicated 6× | **C** — one `SystemUnderTest` gate adapter |
| `claude -p` hardwired | **D** — agent-runtime port |
| `benchmark` key ignored; arms in Python; pins duplicated; budget-unit drift | **E** — a manifest that declares |
| `analyze.py` hardcodes A0-vs-A3 | **F** — declare baseline/treatments |
| flat module dir; heavy per-cell dirs; single-process runner | **G** — reorg + scale |

**The punchline:** the kernel already proved the pattern works six times over. The
fix is not to invent something new — it's to give the seventh axis (benchmark)
the same discipline the first six already have, and then delete the fork that its
absence forced into existence.
