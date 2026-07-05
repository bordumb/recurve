# Running the evals

`eval/` is a **separate** uv project from the engine (`recurvelib` stays
stdlib + PyYAML on purpose) so that measuring recurve never adds a
dependency to recurve itself. Its own claims (`.recurve/claims/eval`,
`EV-1`–`EV-24`) gate every stage below — `recurve matrix --gate` in the repo
root exercises this harness the same way it exercises the engine.

## 0 · Prerequisites

- Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).
- Docker, for the oracle sandbox (`[oracle.env] mode = "docker"`) — the
  oracle grades untouched, generated code, so it runs `--network none` in a
  container the agent workspace never sees.
- API credentials for whichever model(s) a manifest names (e.g.
  `ANTHROPIC_API_KEY` for the Claude adapter).
- From `eval/`: `uv sync --extra run --extra oracle --extra figures` (the
  core pipeline — `plan`/`analyze`/matrix expansion — is stdlib-only and
  needs none of these; they're only required to actually spend money or
  render figures).

Every command below is run from `eval/` unless noted otherwise.

## 1 · Build and pin the oracle image

```bash
eval oracle build eval/experiments/poc-bcb-hard.toml
```

Derives the oracle image from the committed `oracle/Dockerfile.nltk` (the
official BigCodeBench evaluation image plus the NLTK corpora ~27% of tasks
need, so those grade hermetically instead of being excluded) and
**reconciles its digest** against the manifest's pin. A rebuild that
produces a different image ID is a hard mismatch, not a silent adoption —
you either update the manifest's `digest` deliberately (a reviewed,
intentional re-pin) or you have drifted.

## 2 · Calibrate the oracle

```bash
eval calibrate eval/experiments/poc-bcb-hard.toml
```

Grades **every canonical solution** in the benchmark through the finished,
warm-container oracle path and writes a calibration keyed by the resulting
`oracle_env_hash` (`eval/calibrations/<hash>.json`). This is the spend gate's
admission ticket: a canonical solution can never legitimately fail, so any
non-pass here is either a real harness bug (refused, not swallowed) or a
task that must appear in the **pre-registered exclusion table**
(`eval/exclusions/bcb-hard.json`) with a named reason, frozen *before* the
pilot runs. An unexplained failure refuses calibration outright — nothing
downstream can spend money against an oracle that hasn't proven it grades
correctly.

The calibration run also derives the **timeout** used for every real grading
call afterward — from the canonical set's own measured p99, never guessed.

## 3 · Plan the run

```bash
eval plan eval/experiments/poc-bcb-hard.toml --out runs/poc-1
```

Expands the manifest's cross product (tasks × models × arms × budgets ×
seeds) into a pinned `matrix.jsonl` — the full cell list, written **before**
any agent runs (the registered-report affordance: the sample is committed
before results exist, so nobody can retroactively cherry-pick which cells
"count"). Also resolves and locks the oracle environment into
`oracle.lock.json`, and prints the cost ceiling — every cell at full budget,
so the worst case is known before a single dollar is spent.

```
planned 4 cells → runs/poc-1/matrix.jsonl
oracle env locked → runs/poc-1/oracle.lock.json (oeh:e2903a381e9c00beb71381ab2bc72ea1)
cost ceiling (every cell at full budget): $12.00
```

## 4 · Run it

```bash
eval run runs/poc-1 --workers 4
```

Before a single agent invokes, `cmd_run` checks the **spend gate**: it
refuses to run any paid cell unless a calibration exists for *this exact*
`oracle_env_hash`, against *this exact* dataset hash, with the exclusion
table byte-identical to what calibration saw. A refusal here costs nothing —
that asymmetry is deliberate (see [index](index.md)).

Then it starts **one warm oracle container** for the whole run (not one per
grading call — that per-container tax was measured and cut; see the internal
`docs/plans/eval-optimize.md` design note, O1) and drives the matrix as a
resumable work queue: `k` workers, one sealed row appended to `results.jsonl`
per cell. Killing the run and re-invoking `eval run` on the same directory
resumes it — sealed cells are skipped, never re-billed. A grading timeout
gets exactly one serial retry (contention must never read as a false oracle
error), and a hard-kill watchdog bounds total spend independent of any
per-cell budget, because the harness must trust nothing about how a wedged
agent behaves.

Every result row carries its own provenance: `dataset_revision`,
`recurve_commit`, `adapter_version`, `oracle_env_hash`, `seed` — enough to
re-run that one cell in isolation, on its own, later.

## 5 · Analyze

```bash
eval analyze runs/poc-1
```

One deterministic pass, `results.jsonl` → `runs/poc-1/analysis/` (a
`summary.md` with the tables from [index.md](index.md)'s metric list, plus
byte-stable figures — same input, same output bytes, every time, so a
figure diff in review means the *data* changed, never rendering noise).

## Reproducing the O6 smoke test specifically

O6 is the $1, one-task, four-cell smoke that proved the full paid path end
to end (real telemetry, real spend gate, real oracle) before any real POC
money moved — see [Results](results.md) for what it found. To replay it:

```bash
eval oracle build eval/experiments/o6-smoke.toml
eval calibrate eval/experiments/o6-smoke.toml
eval plan eval/experiments/o6-smoke.toml --out runs/o6-replay
eval run runs/o6-replay --workers 1
eval analyze runs/o6-replay
```

`eval/experiments/o6-smoke.toml` pins the exact same single task
(`BigCodeBench/13`, seed 7), the same two models
(`claude-haiku-4-5`, `claude-sonnet-5`), and the same two arms (`A0`, `A3`)
the original run used — the committed `eval/runs/o6/` directory is that
original run's own `matrix.jsonl`/`oracle.lock.json`/`results.jsonl`, kept as
a fixed reference rather than regenerated, so the incident it recorded stays
inspectable byte-for-byte.

## Running the ablation arms (A7–A10)

A7–A10 configure `[gate] adversary=`/`[gate] governor=` per cell — resolved
through the *same* adapter registry the engine itself uses
(`recurvelib.adapters`, wired into `eval/evallib/arms.py` — see
`ablation-infra.md` AI5), not a separate implementation. Add `arms =
["A3", "A7", "A9"]` (etc.) to a manifest's `[matrix]` table; each arm's
resolved config rides in its results rows verbatim. A cross-model adversary
or a review-tier governor pass needs its own reviewer command wired via
`RECURVE_GOVERNOR_CMD` (see the engine's own
[developer guide](../developer_guide/architecture.md)) — an ablation cell
with that unset refuses to silently fall back to the acting agent's own
model, by design.

## Cost and safety guardrails, all load-bearing

- **The spend gate has teeth**: no calibration for the current
  `oracle_env_hash` + dataset hash + exclusion table ⇒ zero cells run.
- **Budget is dollars, not tokens** (`--max-budget-usd`) — a budget-matched
  control across models with very different per-token prices has to be
  matched in the currency that actually matters.
- **Grading concurrency must match the calibration lock** — the harness
  refuses to grade under a concurrency the calibration never measured
  timeouts against.
- **A hard-kill watchdog** bounds total spend independent of any per-cell
  cap — the harness trusts nothing about how a wedged agent behaves.
- **Every stage is a gated recurve claim** (`.recurve/claims/eval`) — before
  changing anything in `eval/evallib/`, `recurve matrix --gate` from the
  repo root is the arbiter, exactly as for the engine itself.
