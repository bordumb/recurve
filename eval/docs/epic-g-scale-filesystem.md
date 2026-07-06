# Epic G — Scale & filesystem

**Leverage:** medium (needed before large runs; module reorg pays down navigation debt).
**Depends on:** Epic A makes the module reorg clean (benchmarks separate out). The
scale/runner tasks are independent.

---

## So what? (plain English)

Three separate concerns under one roof:

1. **Navigation debt.** `evallib/` is a flat folder of ~30 files where the kernel,
   the oracle infra, the analysis, and two benchmarks' worth of modules are all
   mixed together. A newcomer can't tell what's core vs benchmark-specific vs an
   adapter. (Epic A already sketched the target layout.)
2. **Disk footprint.** Every cell gets a full workspace with its own `.git`,
   `.recurve`, and `__pycache__`. It's gitignored, so it won't bloat the repo — but
   it accumulates on disk with no automatic cleanup, and for SWE-bench each cell is
   a *repo checkout + a docker container*, which is far heavier.
3. **Throughput ceiling.** The runner is a single-process `ThreadPoolExecutor`.
   That's fine for a 4-cell smoke, but the real matrices are big — the BCB pilot is
   148 tasks × 2 models × 2 arms = 592 cells; the ablation ladder multiplies arms
   ~5×; SWE-bench Verified is 500 instances. One machine, one process is the
   ceiling, and there's no way to spread a run across machines.

None of this blocks today's smokes. All of it blocks the "full" runs the roadmap
calls for (`eval-roadmap.md`, `eval-full.md`).

## Current state (evidence)

**Flat module dir** — ~20 generic + ~9 `swebench_*` files interleaved (see the map
in [00-diagnosis.md](00-diagnosis.md)).

**Per-cell heavy workspaces:**

```
runs/o6/cells/<cell_id>/          each ~90–220 KB, and each contains:
  .git/  .recurve/  __pycache__/  solution.py  TASK.md  test_probe.py ...
```

4 cells = ~600 KB for a *one-task* smoke; scale linearly to 592 cells ≈ tens of
MB, ×5 arms for ablation, and SWE-bench cells carry a container each. Gitignored
(`eval/.gitignore`: `runs/*/cells/`) so the repo is safe, but nothing tars or GCs
them after seal.

**Single-process runner:**

```python
# evallib/runner.py:79-84
if workers > 1:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(do, todo))                   # one process, one machine
```

The **good news**: the seal design is already distribution-friendly. Rows are
appended + `fsync`'d per cell, and resume skips sealed cell ids
(`runner.py:31-46,63-67`). That means multiple workers — even on multiple machines
— could share one matrix *if* cell claiming were coordinated. The primitive is
there; only the lease is missing.

## Target design

### Module reorg (do right after Epic A)

```
evallib/
  core/        plan.py arms.py orchestrate.py run_pipeline.py runner.py
               calibration.py quarantine.py oracle_env.py oracle_docker.py
               warm_oracle.py oracle_build.py grade_policy.py budget.py watchdog.py
               analyze.py render.py classify.py done_signal.py audit.py materialize.py
  benchmarks/  bigcodebench.py swebench.py        (the Benchmark descriptors, Epic A)
  adapters/    claude.py runtime.py telemetry.py  (agent runtimes, Epic D)
  sut/         recurve.py                          (the SUT gate/init/decide adapter, Epic C)
  cli.py
```

Keep the `runs/<name>/{manifest.toml, matrix.jsonl, results.jsonl, analysis/}`
run layout **exactly as is** — it's one of the best parts of the design.

### Cell workspace lifecycle

- Tar + remove a cell's workspace after its row is sealed (opt-in
  `--keep-workspaces` for debugging). The transcript/workspace is reproducible from
  the sealed row's provenance, so it's safe to discard.
- Document the expected footprint per benchmark so a run doesn't surprise-fill a
  disk mid-batch.

### Shardable work queue (only when a full run is imminent)

- Add a cell **lease**: a worker atomically claims a cell id (a `claims/` dir with
  `O_EXCL` create, or a tiny sqlite) before running it, so N workers/machines share
  one `matrix.jsonl` without double-spending. Merge each worker's `results.jsonl`
  (the seal format already tolerates concatenation + dedupe by `cell_id`).
- This is the *only* change that touches the otherwise-excellent `runner.py`; keep
  the single-process path as the default and the lease path as opt-in.

## Tasks

- [ ] **G1 — Reorg `evallib/` into `core/ benchmarks/ adapters/ sut/`.** Pure
  moves + import updates; no behavior change. Do it as its own commit after Epic A
  so the diff is legible. *Acceptance:* imports resolve; all gated eval claims
  green; `git log --follow` still tracks moved files.

- [ ] **G2 — Post-seal workspace GC.** Tar-and-remove each cell dir after its row
  seals, behind `--keep-workspaces`. *Acceptance:* a full run's peak `cells/`
  footprint is bounded by `workers`, not by total cells; `--keep-workspaces`
  preserves today's behavior.

- [ ] **G3 — Document the footprint.** A short table in `eval/README.md`: per-cell
  disk for BCB vs SWE, and projected totals for pilot/ablation/full. *Acceptance:*
  a reader can size a disk before launching.

- [ ] **G4 (scale, roadmap-gated) — Cell lease for multi-worker runs.** Atomic cell
  claiming + `results.jsonl` merge. *Acceptance:* two runner processes over one
  matrix produce each cell exactly once; resume still works; single-process default
  unchanged.

- [ ] **G5 (scale) — Bound SWE-bench container lifecycle.** SWE cells hold warm
  containers per instance (`swebench_warm.PerInstanceWarmRegistry`). Ensure
  containers are reaped on cell completion and capped in number under high
  `workers`. *Acceptance:* a multi-instance SWE run doesn't leak containers or
  exceed a configured concurrent-container cap.

## Risks & constraints

- **Don't touch the seal/resume invariant.** `runner.py`'s per-cell `fsync` +
  sealed-id skip is what makes long headless runs safe (`runner.py:1-18`). G4 must
  *extend* it (add claiming) without weakening durability.
- **Reorg is a big diff — isolate it.** Land G1 alone, no logic changes, so a
  reviewer can trust it's a pure move. Mixing a move with a behavior change hides
  bugs.
- **Workspace GC vs debuggability.** Discarding workspaces removes the ability to
  post-mortem a weird cell. Default to GC (footprint matters at scale) but make
  `--keep-workspaces` prominent and mention it in any failure output.
- **Determinism of cell ids is what makes sharding safe** (`plan.cell_id`,
  `plan.py:35`). Don't introduce any run-time randomness into cell identity or the
  lease/merge breaks.
