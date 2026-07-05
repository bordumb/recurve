# Evaluation — why, how, and the methodology

recurve's own claim ledger reports footprint: claim counts, one worked wave,
a gate that goes green. That is not the same thing as evidence. The papers
recurve cites as its reference class — AlphaEvolve, λ² — earn their claims
with an external benchmark, an effect size against a baseline, component
ablations, and cost/scaling curves. Until this evaluation program existed,
recurve had never been measured that way.

The one-sentence gap this closes:

> We have never run the same agent, on the same external tasks, with and
> without the gate, and measured **who shipped more bad work**.

Everything in `eval/` exists to produce that number, honestly, and its
ablation decomposition — and to do it while holding the measuring instrument
itself to recurve's own standard: the `eval/` pipeline is a gated recurve
suite (`.recurve/claims/eval`, claims `EV-1`–`EV-24`, all closed), not a
one-off script somebody ran once.

## Architecture

The pipeline is built around one rule: anything that can change a verdict is
pinned before a single paid cell runs, and every cell's provenance — task,
model, arm, resolved gate config, budget — travels with its result row. The
diagram below is the shape that rule produces, from a human-authored
manifest down to the analysis that reads `results.jsonl`:

```mermaid
flowchart TD
    M["manifest.toml<br/>tasks + models + arms + budgets + seeds"]
    OB["eval oracle build<br/>derive + pin the oracle image digest"]
    CAL["eval calibrate<br/>grade every canonical solution<br/>write calibration keyed by oracle_env_hash"]
    PLAN["eval plan<br/>expand task x model x arm x budget x seed"]
    REG[("recurvelib.adapters registry<br/>ADVERSARY_ADAPTERS / GOVERNOR_ADAPTERS")]
    MTX[("matrix.jsonl<br/>pinned cells")]
    LOCK[("oracle.lock.json<br/>digest, platform, timeout")]
    GATE{"spend gate<br/>calibration passing?"}
    REFUSE["refused: zero cells run"]
    RUN["eval run<br/>resumable work queue"]
    CELL["one cell's workspace<br/>A0 bare, or A3+ recurve-init'd<br/>with the arm's resolved config"]
    AGENT["AGENT_CMD adapter<br/>e.g. claude -p ..."]
    DECL{"agent declares done<br/>or budget exhausted"}
    WARM[["warm oracle container<br/>one per run, not per cell"]]
    ORACLE["oracle quarantine<br/>held-out tests, isolated container<br/>network: none"]
    RES[("results.jsonl<br/>one row per cell, full provenance")]
    AN["eval analyze<br/>FDR, ΔFDR, price of trust<br/>Wilson CIs, McNemar"]
    SUM["summary.md + figures"]

    M --> OB --> CAL
    M --> PLAN
    PLAN -- "A7-A10 resolve adversary=/governor=" --> REG
    REG -- "resolved config, recorded verbatim" --> PLAN
    PLAN --> MTX
    PLAN --> LOCK
    CAL --> GATE
    MTX --> GATE
    LOCK --> GATE
    GATE -- refuses --> REFUSE
    GATE -- admits --> RUN
    RUN --> CELL --> AGENT --> DECL --> ORACLE
    WARM -. docker exec .-> ORACLE
    ORACLE --> RES
    RUN --> RES
    RES --> AN --> SUM
```

Three things to notice in that shape:

- **The manifest never talks to the registry directly.** An arm like A7
  (`adversary=cross_model`) or A10 (`adversary=cross_model` +
  `governor=mechanical_review`) is just a name until `eval plan` resolves it
  through the same `recurvelib.adapters` registry that `recurve`'s own
  `[gate]` config uses — so a plan that names an unknown adapter fails at
  `plan` time, not mid-run.
- **The spend gate sits between planning and spending.** `eval calibrate`
  must already show a passing grade of every canonical solution, keyed to
  the exact oracle-environment hash the run will use, or `eval run` refuses
  to start a single paid cell.
- **The oracle never shares a container with the agent.** The agent process
  has already exited (declared done, or hit its budget) before the harness
  hands the solution to the quarantined oracle container, which runs with
  no network access — so a held-out test can never leak into the agent's
  turn, and the harness's own defects only ever bias *toward* more reported
  failures, never fewer (see the reproducibility rule below).

## Why: the quantities that matter

Let a *task* carry a **held-out oracle** — a test the agent never sees. An
*arm* is a configuration (gate components × model × budget). Per task-run,
the agent eventually **declares done** (or exhausts its budget); the harness
then applies the oracle, quarantined in its own environment, after the agent
process has already exited.

- **False-done rate (FDR)** — the headline quantity: `FDR = P(oracle fails |
  arm declared done)`. Compared across arms, `ΔFDR = FDR(no-gate) −
  FDR(gate)` is the effect size the whole program exists to produce.
- **Oracle pass@budget** — `P(oracle passes | token budget ≤ B)`, plotted
  over a budget grid: does the gate's overhead cost outcomes, or buy them?
- **Price of trust** — `tokens(gate arm) / tokens(no-gate arm)` and the
  matching wall-clock ratio, reported next to ΔFDR so the trade is one
  glance, never buried.
- **Gate-rejection rate** — from run records: `Σ attempts − closes`, the
  operational rate at which an agent believes it is done and the gate
  refuses.
- **Interception confusion matrix** (seeded defects) — per gate layer L:
  `TPR_L` (blocks a real defect), `FPR_L` (blocks a known-good change), and
  **marginal detection** `TPR_L − TPR_{L−1}` — what each additional layer
  catches that the previous stack missed.
- **Miss-correlation ρ** — over seeded defects graded by both an actor
  configuration and an adversary configuration: `ρ = P(adversary misses |
  actor missed) / P(adversary misses)`. `ρ ≈ 1` means independent failures;
  `ρ ≫ 1` means the actor and its checker share a blind spot. This is the
  quantity the internal `oracle-strength-and-decorrelation` and
  `ablation-infra` design docs (`docs/plans/`) give a concrete, gated engine
  mechanism to — see [Results](results.md) for the live incident that
  motivated them.

Statistics throughout: paired design (same tasks, every arm), McNemar's test
on paired pass/fail deltas, Wilson 95% intervals on every rate, raw fractions
always shown alongside a percentage — never a bare two-significant-figure
number on single-digit n.

## How: the arm ladder, not a factorial

Every ablation is a **configuration** of the same engine — a `recurve.toml`
+ flags — never a fork of the CLI, so an arm is fully reproducible from its
own results row (the resolved `[gate]` config is recorded verbatim, not just
an arm label). The full cross product of every switch runs into the
hundreds of arms and is deliberately not attempted; instead the matrix is a
**ladder plus leave-one-out**, extended (not replaced) as new switches are
built:

```
A0  no-recurve                       — agent + task, declares done itself (the control)
A1  plain-CI                         — agent + the repo's own test suite as CI gate
A2  recurve, traps off               — claims + probes, RED-first disabled
A3  recurve full                     — claims + probes + traps (default discipline)
A4  A3 + fuzz/iso/diff               — hardened probes
A5  A3, write boundary off           — what the write boundary is worth
A6  A3, controller off               — what external stopping is worth
A7  A3 + adversary=cross_model       — per-claim decorrelation alone
A8  A3 + governor=mechanical         — free run-level re-execution check alone
A9  A3 + governor=mechanical_review  — run-level decorrelated review alone
A10 A3 + adversary=cross_model
       + governor=mechanical_review  — the full decorrelation stack
```

A0→A3 is the effect-size story; A2/A5/A6 vs A3 attribute value to each
component; A4 measures the hardening margin; A7–A10 measure the marginal
value of per-claim adversary review vs. run-level governor review vs. both
together. The POC scope is `{A0, A3}` only — A7–A10 are the ablation-phase
arms, gated on the adapters `ablation-infra.md` built.

## The reproducibility design rule

> Anything that can change a verdict must be pinned and refused-on-drift.
> Anything that can change a timing must be recorded. The manifest is human
> intent; the lock is machine-resolved truth.

Three things can silently change a number; each is pinned and recorded:

| Citizen | Intent (the manifest) | Resolution (locked at plan time) | Refuses on drift |
|---|---|---|---|
| Dataset | `[tasks]` benchmark + revision | local JSONL + content hash + count | a hash/count mismatch is rejected |
| Model | `[matrix]` models | frozen into `matrix.jsonl` before any run | cell ids derive from coordinates |
| Oracle env | `[oracle.env]` mode + image + digest | `oracle.lock.json` (image **digest**, platform, container Python, wrapper hash, resolved timeout, exclusion-table hash) | a digest mismatch, or a bare mutable `:tag`, is refused outright |

Every harness defect in this design fails in **one direction**: a correct
real solution turning into an error reads as an oracle failure, which
inflates shipped-bad-work — the paper's own headline. A broken harness
silently *confirms* the thesis rather than contradicting it, which is why
the rule is strict, and why a **calibration gate** stands before any paid
run: all canonical solutions are graded through the finished oracle path
first, keyed to the oracle-env hash, and no paid cell runs while that pass
rate is red.

## Where to go next

- **[Running the evals](running.md)** — the exact commands, in order, to
  reproduce any run in this repo (or plan a new one) from a clean clone.
- **[Results](results.md)** — what has actually been run so far, the real
  numbers, and the one incident (O6) that already came out of this
  pipeline and reshaped the engine itself.
