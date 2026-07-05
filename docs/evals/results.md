# Results

**Status, honestly, up front:** as of this writing, exactly one real,
paid run exists — **O6**, a $1-scale smoke test (one task, four cells).
The full POC (BigCodeBench-Hard × {Haiku 4.5, Sonnet 5} × {A0, A3}, 50–148
tasks) and the ablation-phase study (A7–A10) specified in
[index.md](index.md) have **not been run yet**. This page reports exactly
what exists — real numbers from a real run — and is explicit about what
doesn't exist so nobody mistakes a smoke test for the headline study.

## O6 — the live smoke test

**Question asked:** does the full paid pipeline — real models, real spend
gate, real oracle container, real telemetry — produce analyze-ready rows at
all, before any real money moves on the actual POC? One task
(`BigCodeBench/13`), two models, two arms, sequential grading, spend ceiling
$2.

| Model | Arm | Declared done | Gate outcome | Oracle verdict | Tokens in | Tokens out |
|---|---|---|---|---|---|---|
| claude-haiku-4-5 | A0 (no recurve) | true | — | **pass** | 141,524 | 2,211 |
| claude-haiku-4-5 | A3 (100% recurve) | **false** | `process_failed` | fail | 6,726,157 | 31,532 |
| claude-sonnet-5 | A0 (no recurve) | true | — | **pass** | 1,142,888 | 8,874 |
| claude-sonnet-5 | A3 (100% recurve) | **true** | `declared` | **fail** | 4,892,688 | 37,050 |

(`eval/runs/o6/results.jsonl`, kept committed as a fixed reference — see
[Running the evals](running.md) to replay it.)

Both A0 cells passed the held-out oracle cleanly. Both A3 cells failed it —
for two different, both real, reasons.

### Finding 1 — the incident that motivated this whole engine wave

`claude-sonnet-5` / A3: `declared_done=true`, `gate_outcome="declared"`,
`terminal_state={"gate": "green", "stop_reason": "gate_green"}` —
**and** `oracle_verdict="fail"`.

The agent authored its own claim and its own RED-first probe directly from
the task statement (it never sees `BigCodeBench/13`'s hidden test suite),
closed it, and `recurve matrix --gate` went green — by every rule the gate
enforces, honestly applied. BigCodeBench's held-out oracle, applied after
the fact, says the solution is wrong. Same model wrote the code and the
check that approved it; the misreading that produced the bug and the
misreading that failed to catch it were the same misreading.

This is not a hypothetical the framework's papers gesture at — it is the
literal, first live cell, before a single row of the actual POC existed.
Recurve's ledger, as it stood *before* this evaluation ran, had no way to
render this claim any differently from one that survived an independent
check: both are just "GREEN."

**What happened as a direct result:** this incident is the concrete case
named in `docs/plans/oracle-strength-and-decorrelation.md` (§1, "Why now") —
which specifies an oracle-tier vocabulary that makes *what backed* a GREEN
visible, a verified cross-model adversary, and a run-level governor that can
supersede a run's own STOP_SUCCESS — and in `docs/plans/ablation-infra.md`,
the ports/adapters architecture that makes those mechanisms real adapters
rather than one-off code. Both PRDs are now implemented and gated (suites
`decorrelation` and `ablation`), and each includes a regression fixture that
**replays this exact incident** against the real adapters:

- Claim level (`decorrelation/DC-3`): the same same-model
  actor-and-prober-agree shape, run through a real `cross_model` adversary —
  the disagreement surfaces, and the proposed counterexample is validated by
  the engine's own capture rule as genuine, not noise.
- Run level (`decorrelation/DC-4`): the same shape as a full cycle — the
  free `mechanical` governor tier correctly does *not* catch it (that's not
  its job); the `mechanical_review` tier does, vetoing with a captured,
  re-checkable reason.

Run `recurve probe --suite decorrelation --gap DC-3` (and `DC-4`) from the
repo root to see both pass GREEN today.

### Finding 2 — a runaway-spend bug, also real

`claude-haiku-4-5` / A3 spent **6,726,157 input tokens** against a
60,000-token intended budget — over 100× — before exhausting its cap
without ever reaching a formal `recurve matrix --gate` declaration
(`gate_outcome="process_failed"`, `terminal_state.stop_reason
="budget_exhausted"`, despite the gate itself reading green at that
moment). A weak model, given an autonomous retry loop and a token-counted
rather than dollar-counted budget, can burn spend far outside the number an
experimenter actually authorized.

This is the incident named directly in the `eval` suite's own claims:
`EV-23` ("budget-matched control is dollars, not tokens") re-expresses every
arm's cap in the currency that actually bounds spend, and `EV-24` (a
hard-kill watchdog) bounds total spend independent of any per-cell
accounting, trusting nothing about how a wedged agent behaves. Both are
closed, gated claims today — see [Running the evals](running.md)'s
guardrails section.

### What O6 did and did not prove

- **Proved:** the full paid path — real model calls, the spend gate, a warm
  oracle container, telemetry — produces analyze-ready, correctly-shaped
  rows end to end. The pipeline itself works.
- **Proved:** two real, previously-latent bugs exist and are now named,
  gated claims with kept counterexamples (correlated authorship; runaway
  token spend).
- **Did not prove:** anything about ΔFDR, price of trust, or the
  model×gate interaction — a sample size of one task cannot support any of
  index.md's headline statistics. That is what the POC run (next) is for.

## What has not been run yet

- **The POC** (`eval/experiments/poc-bcb-hard.toml`): BigCodeBench-Hard ×
  {Haiku 4.5, Sonnet 5} × {A0, A3}, pinned-seed n=50 pilot before the full
  148. Estimated cost **~$100–300**. This is the run that produces the
  first real ΔFDR, oracle-pass@budget, and price-of-trust numbers.
- **The ablation phase** (A7–A10): per-claim cross-model adversary alone,
  run-level mechanical governor alone, run-level review-tier governor
  alone, and the full stack — now buildable for real, since the adapters
  and registry these arms resolve through (`recurvelib.adapters`,
  `eval/evallib/arms.py`) are implemented and gated as of this session's
  work. No cells have been run against them yet.
- **E1 (interception confusion matrix)**: CPU-only, no API cost, not yet
  built.
- **A task tier at recurve's actual working scale** — long-running,
  multi-file, multi-hour planning work, as opposed to BigCodeBench-Hard's
  single-function tasks — is not yet designed at all. See [index.md's scope
  and limitations section](index.md#scope-and-limitations-what-these-tasks-can-and-cannot-tell-us)
  for why, and what would have to be true for it to exist without
  circularity.

## Reproducing or extending these numbers

See [Running the evals](running.md) for the exact commands — `eval oracle
build` → `eval calibrate` → `eval plan` → `eval run` → `eval analyze` — and
the specific replay recipe for O6. Every row above carries its own
`dataset_revision`, `recurve_commit`, `adapter_version`, and
`oracle_env_hash`, so any single cell is independently re-runnable without
re-running the whole matrix.
