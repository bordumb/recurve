# Eval POC — two models, one benchmark, 0% vs 100% recurve

> The minimal experiment that proves the evaluation pipeline and produces
> the first real ΔFDR numbers: **Claude Haiku 4.5 and Claude Sonnet 5**,
> each run **with and without** recurve, on **BigCodeBench-Hard**, judged by
> a held-out oracle the agent never sees. This document is self-contained:
> everything needed to build and run the POC is here. The full evaluation
> program (ablation arms, provider matrix, E1–E6 experiments, phasing) lives
> in [eval-full.md](eval-full.md); the arm names A0/A3 come from its arm
> matrix.

## 1 · The experiment

Two models × two arms (**0% recurve** vs **100% recurve**), one benchmark:

- **Claude Haiku 4.5** (`claude-haiku-4-5`) — the weak/cheap end. If the
  hypothesis "the gate's value is largest for weaker models" is right, this
  is where the effect is biggest.
- **Claude Sonnet 5** (`claude-sonnet-5`) — the mid-tier control. The
  counter-hypothesis is that weak models are also the *worst at operating*
  the gate (authoring claims/probes/traps is multi-step discipline), so the
  value-vs-model-strength curve may be an inverted U rather than monotonic.
  Two models give the first two points on that curve and de-risk the
  "Haiku couldn't drive the harness" confound.

Same pinned task set for all four cells, so every comparison is paired:
arm effect within each model (ΔFDR per model), and the model×gate
interaction across them (does the gate help Haiku more than Sonnet?).

## 2 · Benchmark choice: BigCodeBench-Hard

**Recommendation: `bigcode/bigcodebench-hard` (148 tasks, HuggingFace).**
Why it beats the alternatives *for this POC specifically*:

| Candidate | Verdict for POC |
|---|---|
| HumanEval+ / MBPP+ | ✗ too easy + contaminated — Haiku near ceiling, no headroom for a delta to show up |
| SWE-bench Lite/Verified | ✗ for POC (✓ for phase 2) — most credible substrate, but docker-image-per-task, long trajectories, and a weak model in a large repo = slow, expensive, noisy first run |
| LiveCodeBench | ◐ good backup — clean stdin/stdout oracle, contamination-resistant, but algorithmic puzzles fit the claims/probes model less naturally |
| **BigCodeBench-Hard** | ✓ realistic library-usage tasks; small models fail often (real headroom for ΔFDR); each task carries its own hidden `unittest` suite in the dataset (`test` field) = a ready-made held-out oracle; one shared environment for all tasks (no per-task docker); official eval harness exists (`pip install bigcodebench`) |

Exact sources: dataset <https://huggingface.co/datasets/bigcode/bigcodebench-hard>,
harness <https://github.com/bigcode-project/bigcodebench>. Pin the dataset
revision hash in the loader claim.

## 3 · The two arms

Every cell runs through the existing BYO-agent seam —
`claude -p --bare --permission-mode bypassPermissions --model <model>` with
`<model>` ∈ {`claude-haiku-4-5`, `claude-sonnet-5`} — under an **identical
token cap** per task (budget-matched across arms *and* across models; start
at 60k tokens/task, revisit after the pilot).

- **Arm A0 — 0% recurve.** Fresh workspace containing only the task
  statement (`instruct_prompt`) and an empty `solution.py`. The agent solves
  the task however it likes (it may write and run informal tests) and exits.
  Exiting with a non-empty solution = *declared done*.
- **Arm A3 — 100% recurve.** Same workspace, but `recurve init`-ed. The
  agent must express the task as a claim with a **RED-first probe it authors
  itself from the task statement** (its own tests — it never sees the hidden
  suite) plus **at least one trap** (a deliberately wrong implementation the
  probe must reject), then burn down until `recurve matrix --gate` is green.
  Gate green = *declared done*; budget exhausted with a red gate = *refused
  to declare* (this is the gate doing its job — count it, don't hide it).

## 4 · Oracle quarantine and metrics

The dataset's hidden `test` field **never enters either workspace**. After
the agent process exits, a separate evaluator venv (built once from the
bigcodebench requirements) runs the hidden unittest suite against the final
`solution.py`. Flake control: 3× oracle runs, majority verdict, flake rate
reported.

Per cell (model × arm), over the same pinned task set:

- **Shipped-bad-work rate** (headline): `P(declared done ∧ hidden tests fail)`
  — this is what the gate exists to prevent, and it handles the asymmetry
  that A3 sometimes refuses to declare.
- **FDR** (false-done rate) conditional form: `P(hidden fail | declared done)`;
  `ΔFDR = FDR(A0) − FDR(A3)` per model is the effect size.
- **Oracle pass rate** at the matched budget (does the gate's overhead cost
  outcomes?).
- **Price of trust**: tokens, cost (Haiku: $1/M in, $5/M out; Sonnet:
  $3/M in, $15/M out), wall-clock, A3/A0 ratios per model.
- **Gate activity in A3**: rejections (attempts − closes), refused-to-declare
  count, and — for each A0 shipped-bad task — whether A3 on the same task
  passed, refused, or also shipped bad (the paired table, per model).
- **Process-failure vs gate-refusal split** in A3: a run that never produced
  a well-formed claim/probe/trap is a *harness-operation failure*, not the
  gate catching bad work — the two must be reported separately or the weak
  model's numbers are uninterpretable.
- **Model×gate interaction**: ΔFDR(Haiku) vs ΔFDR(Sonnet) — the first
  two-point read on whether gate value falls, rises, or peaks with model
  strength.

Stats: all 148 tasks (or a pinned-seed n=50 pilot first), paired design,
McNemar on paired oracle outcomes within each model, Wilson 95% intervals on
rates, raw fractions always shown. Estimated cost: ~148 tasks × 2 arms ×
≤60k tokens ≈ $25–75 for the Haiku pair and ~3× that for the Sonnet pair —
**~$100–300 total**; wall-clock manageable by running ~8 tasks concurrently.

## 5 · Build this first: the `eval/` pipeline (matrix as data)

The POC does not get built as a one-off script. **Before any cell runs, the
`eval/` pipeline below exists and its claims are GREEN** — then the POC is
nothing but the first manifest fed through it. Design principle: **the
matrix is data, not code.** An experiment is declared in a small manifest;
everything downstream is a pure function of it — so scaling to the full
program later (more models, more arms) is a config change, not new code.

**Three verbs, with a file between each** (every phase boundary is an
inspectable, diffable artifact):

- `eval plan` — expands the manifest's cross product into `matrix.jsonl`,
  the pinned cell list (task × arm × model × budget × seed), written
  **before** any agent runs (the registered-report affordance: the sample
  is committed before results exist). Prints the cost estimate.
- `eval run` — a resumable work queue over the cells: k workers, one sealed
  row per cell. Cell IDs derive from their coordinates, so an interrupted
  run resumes by skipping sealed cells; re-running is always safe.
- `eval analyze` — deterministic: `results.jsonl` in, tables out. No
  notebook state, no manual steps.

**Layout** (own uv project at the repo root; `recurvelib` never imports it,
so the engine's stdlib+PyYAML posture is untouched):

```
eval/
  pyproject.toml               # own uv project — recurvelib never imports it
  README.md                    # how to reproduce any run, end to end
  evallib/                     # infrastructure
    taskstore.py               #   fetch + pin benchmarks (HF revision, git commit)
    materialize.py             #   task → fresh workspace (A0 / A3 variants)
    arms.py                    #   arm name → recurve.toml + flags (pure)
    adapters/claude.py         #   the AGENT_CMD wrapper (--model param)
    adapters/telemetry.py      #   uniform token/cost capture + dated price table
    runner.py                  #   matrix → work queue → sealed cell rows
    quarantine.py              #   held-out oracle, separate venv, 3× majority
    analyze.py                 #   results.jsonl → McNemar / Wilson / paired table
  experiments/                 # one manifest per experiment — small, committed
    poc-bcb-hard.toml
  runs/                        # one immutable dir per launch: {date}_{experiment}
    2026-07-XX_poc-bcb-hard/
      manifest.toml            #   frozen copy of the manifest at launch time
      matrix.jsonl             #   the expanded cells, pinned BEFORE running
      cells/                   #   per-cell workspaces + transcripts (gitignored)
      results.jsonl            #   one row per cell (committed — this is the data)
      analysis/summary.md      #   generated tables (committed)
```

**The POC manifest** (`eval/experiments/poc-bcb-hard.toml`) is the whole
experiment in ~15 lines:

```toml
[experiment]
name = "poc-bcb-hard"
question = "Does the gate reduce shipped-bad-work at matched budget?"

[matrix]
models  = ["claude-haiku-4-5", "claude-sonnet-5"]
arms    = ["A0", "A3"]
budgets = [60000]
seeds   = [0]

[tasks]
benchmark = "bigcodebench-hard"
revision  = "<pinned HF revision hash>"
sample    = { n = 50, seed = 7 }   # pilot; "all" for the full 148

[oracle]
runs = 3
verdict = "majority"
```

**Reproducibility rules:**

1. **Runs are immutable** — never overwrite a run dir; a re-run is a new
   dated dir; the frozen manifest copy keeps old runs legible even after
   `experiments/` evolves.
2. **Every results row carries its own provenance** — dataset revision,
   model version string verbatim, recurve commit, adapter version, seed.
   Any single row is re-executable from its own fields.
3. **Commit policy** — manifests, `matrix.jsonl`, `results.jsonl`, and
   `analysis/` are committed (small; they are the evidence); `cells/`
   workspaces and transcripts are gitignored (tarballed on demand).
4. **A run dir reads like a lab notebook**, top to bottom: manifest (what
   we intended) → matrix (what we planned) → results (what happened) →
   analysis/summary.md (what it means) — compared against the §8
   pre-registered guesses.
5. **No sweep frameworks** (hydra/wandb) — manifest + queue + JSONL gives
   the same matrix semantics with nothing hidden, which matters when the
   pipeline's credibility is the product.

**The gateable claims** (an `eval` suite in the ledger — the instrument is
held to the standard it measures), mapped to modules:

1. **TaskStore** (`taskstore.py`) —
   `datasets.load_dataset("bigcode/bigcodebench-hard")` pinned to a revision
   hash; probe asserts the hash and task count.
2. **Materializer** (`materialize.py` + `arms.py`) — task → fresh workspace
   (git-init'd tmpdir; the A3 variant adds `recurve init` + the arm's
   config); trap: a workspace that contains the hidden `test` text must be
   refused.
3. **Runner** (`runner.py` + `adapters/`) — drives the adapter under the
   token cap; seals one row per cell; trap: a re-run over a completed matrix
   must produce zero new agent invocations (resume correctness).
4. **Quarantine evaluator** (`quarantine.py`) — separate venv + 3× unittest
   majority; trap: a tampered oracle (edited `test` text) must be caught by
   a checksum against the pinned dataset.
5. **Analysis** (`analyze.py`) — deterministic: `results.jsonl` in → the
   §4 tables + paired McNemar out; probe: byte-stable output given the
   same input.

## 6 · Order of operations

1. Write the POC PRD, `recurve admit` it, author the five `eval` suite
   claims RED-first, baseline them.
2. Burn down until the `eval` suite is GREEN — the pipeline now exists and
   is gated.
3. `eval plan experiments/poc-bcb-hard.toml` (n=50 pilot) → review
   `matrix.jsonl` and the printed cost estimate before spending anything.
4. Pilot: `eval run` (~8 workers) → `eval analyze`. Inspect the
   process-failure split first — if harness-operation failures dominate the
   A3 cells, iterate the A3 cycle prompt/skill **once**, record the change,
   and re-run the pilot as a new run dir (the iteration is data, not
   embarrassment).
5. Full run: set `sample = "all"` (148 tasks), fresh run dir.
6. `eval analyze` → compare against the §8 guesses in
   `runs/<id>/analysis/summary.md`.
7. Feed the tables into the paper's §5 and decide whether E2 (SWE-bench
   Verified, more providers — see [eval-full.md](eval-full.md)) is next.

## 7 · What the POC does and doesn't prove

Proves: the pipeline end-to-end (fetch → materialize → run → quarantine →
analyze), a first directional ΔFDR on an external benchmark with a real
held-out oracle, and a first read on the model×gate interaction. Doesn't
prove: generality (two models, one benchmark — the full matrix is E2/E4's
job), contamination-immunity (BigCodeBench predates both models' cutoffs;
the paired design means all cells share the advantage, and the LiveCodeBench
sensitivity arm comes later). **A ΔFDR ≈ 0 result is a result — it gets
reported, not shelved.**

## 8 · Pre-registered guesses (written 2026-07-04, before any run)

Recorded so the POC can surprise us honestly:

1. A0-Haiku ships bad work on ~75–80% of tasks (declares done almost
   always; solve rate in the 15–25% band).
2. ΔFDR(Haiku) is real but modest — 10–20 points — driven more by
   *refusals* than by catch-and-fix; genuine catch→repair→oracle-pass is
   the smallest bucket of the paired table (correlated authorship: the
   same misreading writes both the solution and the probe).
3. A meaningful share of A3-Haiku runs fail on *harness operation*, not on
   the task — this is why the process-failure split in §4 exists, and it
   likely forces one prompt/skill iteration after the pilot.
4. Sonnet: lower A0 shipped-bad (~45–65%), cleaner harness operation, and
   the open question — whether ΔFDR(Sonnet) is smaller than ΔFDR(Haiku)
   (monotonic hypothesis) or larger (inverted-U: gate value peaks where the
   model is strong enough to drive the loop but weak enough to need it).
5. Price of trust: A3/A0 token ratio 3–5× for both models.
