# Evaluation architecture — measuring recurve the way the papers we cite measure themselves

> Purpose: AlphaEvolve and λ² earn their claims with external benchmarks,
> effect sizes against baselines, component ablations, and cost/scaling
> curves. recurve currently reports footprint (claim counts, one worked
> wave). This document is the architecture for closing that gap: **what is
> missing, what we measure, how the pipeline is built, where the benchmarks
> come from, and what has to change in recurve itself** (very little — the
> BYO-agent seam already makes the pipeline provider-agnostic; the ablations
> are config switches, most of which exist).
>
> Everything here is buildable as gated claim waves — the evaluation harness
> is itself a recurve target, so the instrument that measures the framework
> is held to the framework's own standard.

---

## 1 · What is missing, exactly

Mapping the four dimensions of the reference papers onto recurve:

| Dimension | What they have | What we're missing | What fills it (this doc) |
|---|---|---|---|
| External benchmark | AlphaEvolve: 50+ open problems, prod systems. λ²: 40+ synthesis tasks | Any task set not authored by us | §3: SWE-bench Verified, Defects4J/BugsInPy, HumanEval+/MBPP+, LiveCodeBench, miniF2F/PutnamBench |
| Effect size vs baseline | improved/matched counts; % solved vs prior tools | A control arm: the same agent *without* the gate | §5 arms: gate-off, plain-CI, gate-on; headline = **false-done rate delta** |
| Ablations | evolution off / context off / model size | Component-off switches wired into an arm matrix | §4: the ablation switch inventory (5 exist, 3 to build) |
| Scaling / cost curves | compute budget vs quality | Budget-capped runs + token/wall-clock telemetry per arm | §6: budget grid × pass-rate curves; price-of-trust |

The one-sentence gap: **we have never run the same agent, on the same
external tasks, with and without the gate, and measured who shipped more bad
work.** Everything below exists to produce that number and its ablation
decomposition, credibly.

## 2 · The quantities we measure (definitions first)

Let a *task* have a **held-out oracle** O (tests the agent never sees). An
*arm* is a configuration (gate components × model × budget). Per task-run,
the agent eventually **declares done** (or exhausts budget); the harness then
applies O.

**Primary metrics**

- **False-done rate (FDR)** — the self-deception rate, the paper's central
  quantity: `FDR = P(O fails | arm declared done)`. Compared across arms:
  `ΔFDR = FDR(no-gate) − FDR(gate)` is the headline effect size.
- **Oracle pass@budget** — `P(O passes | token budget ≤ B)`, plotted over a
  budget grid → the scaling/cost curve (gate arms pay overhead; the question
  is whether verified-pass at matched budget still dominates).
- **Interception confusion matrix** (M1, seeded defects): for each gate
  layer L: `TPR_L = P(gate blocks | seeded defect)`,
  `FPR_L = P(gate blocks | known-good change)`, and **marginal detection**
  `TPR_L − TPR_{L−1}` — what each layer catches that the previous stack
  missed. This is the component-attribution table.
- **Price of trust** — `tokens(gate arm) / tokens(no-gate arm)` and
  wall-clock ratio at matched task set; reported next to ΔFDR so the trade
  is one glance.
- **Gate-rejection (calibration) rate** — from run records:
  `rejections = Σ attempts − closes`; the operational rate at which agents
  submit work they believe done and the gate refuses.
- **Miss-correlation (decorrelation residue)** — over seeded defects
  evaluated by both an actor-config and an adversary-config:
  `ρ = P(adversary misses | actor missed) / P(adversary misses)`; ρ≈1 means
  independent, ρ≫1 means correlated failures. Run same-model vs cross-model.

**Statistics.** Same tasks across all arms (paired design). Pass/fail deltas:
McNemar's test; rates carry Wilson 95% intervals; n ≥ 50 per cell for the
headline claims, n ≥ 20 for ablation cells (report CIs regardless; never a
bare two-significant-figure percentage on single-digit n). Every run pinned:
model version string, recurve commit, task revision, seed.

## 3 · Benchmark substrate — where tasks and oracles come from

Two properties qualify a benchmark here: (a) a **machine-checkable held-out
oracle**, (b) tasks we didn't author. Sources, by role:

| Benchmark | Source | Size | Held-out oracle | Role here | Cost/run |
|---|---|---|---|---|---|
| **SWE-bench Verified** | HuggingFace `princeton-nlp/SWE-bench_Verified` (+ official harness, github `SWE-bench/SWE-bench`) | 500 human-validated real GitHub issues | FAIL_TO_PASS + PASS_TO_PASS tests, run in the official docker images | **The flagship A/B substrate** (M2): real repos, real defects, trusted oracle | High (docker builds, agent runs) |
| SWE-bench Lite | HF `princeton-nlp/SWE-bench_Lite` | 300 | same | cheaper pilot of the same design | Med |
| **HumanEval+ / MBPP+** | HF `evalplus/humanevalplus`, `evalplus/mbppplus` (evalplus harness) | 164 / ~400 fn-level | extended hidden test suites | **Smoke tier**: cheap end-to-end pipeline validation; NOT headline material (contaminated, small) | Low |
| BigCodeBench | HF `bigcode/bigcodebench` | ~1.1k | hidden tests, library-usage tasks | mid-tier realism between EvalPlus and SWE-bench | Med |
| **LiveCodeBench** | HF `livecodebench/*` (rolling releases) | rolling | hidden tests, post-cutoff problems | **contamination sensitivity arm**: re-run headline cells on post-training-cutoff tasks; if effects vanish, contamination was doing the work | Med |
| **Defects4J** | github `rjust/defects4j` (Java) | 835 real bugs | dev-written failing→passing tests | **M1 with *real* defects**: interception on human bugs, not synthetic mutants | Med |
| BugsInPy | github `soarsmu/BugsInPy` (Python) | ~500 real bugs | same pattern | Python twin of Defects4J; closer to our tooling | Med |
| mutmut / cosmic-ray | PyPI tools | unbounded | mutants are known-bad by construction | **M1 synthetic tier**: seeded-defect generation at volume, per-layer ablations | Low |
| **miniF2F** | github `openai/miniF2F` (Lean4 ports exist; verify exact repo at build time) | 488 olympiad statements | the Lean kernel | **strong-oracle track**: the oracle-spectrum thesis measured at its strong end | Med |
| PutnamBench | github `trishullab/PutnamBench` | ~600 | Lean/Isabelle/Coq kernels | harder strong-oracle tier | High |

Notes: exact HF dataset revisions get **pinned by a probe** (the loader
claim asserts a specific dataset revision hash — benchmarks are evidence, so
they're version-pinned like everything else). Defects4J/BugsInPy are cloned
at pinned commits. Where I've flagged "verify at build time," the first
harness claim does the verification.

## 4 · Ablation design — what we switch off, and what that requires

The reviewers' question "do we ablate CLI components?" — yes, but **never by
editing the CLI**: every ablation is a *configuration* of the same engine, so
an arm is a `recurve.toml` + flags, reproducible from the results row.

**The switch inventory:**

| Layer / mechanism | Switch | Status |
|---|---|---|
| Traps (RED-first enforcement) | `[gate] traps = "off"` | **exists** |
| Fuzz pass | `drill --fuzz` + `[drill] fuzz_n/fuzz_fpr_max` | **exists** |
| Iso pass | `drill --iso` + knobs | **exists** |
| Differential (reference oracles) | `drill --diff` + per-claim `reference:` | **exists** |
| Oracle waivers | `oracle_waiver` per claim | **exists** |
| Probes at all (gate → plain agent) | omit recurve entirely (control arm) | trivial |
| **Write boundary off** (agent may edit probes) | needs a flag on the runtime World boundary | **to build** (one config knob; the boundary lives in `adapters.py`) |
| **Fresh-agent-per-cycle off** (one long-context agent instead) | needs a burndown-runner mode | **to build** (harness-level, not engine) |
| **Controller off** (stop when the agent says done) | needs a runner mode that trusts the run-record's own summary | **to build** (harness-level) |

The three to-build switches are deliberately **harness-or-flag level**, not
engine forks — each is a gateable claim ("with `boundary = off` the agent can
modify probe files and the gate records that the run was unprotected"), and
each ships with a trap.

**The arm matrix** (headline experiment):

```
arms = {
  A0  no-recurve          — agent + task, declares done itself   (control)
  A1  plain-CI            — agent + repo's own test suite as CI gate, no claims/traps
  A2  recurve, traps off  — claims + probes, RED-first disabled
  A3  recurve full        — claims + probes + traps (default discipline)
  A4  A3 + fuzz/iso/diff  — hardened
  A5  A3, boundary off    — measures what the write boundary is worth
  A6  A3, controller off  — measures what external stopping is worth
}
```

A0→A3 is the effect-size story; A2/A5/A6 vs A3 are the component
attributions; A4 measures the hardening margin. Not every benchmark runs
every arm (cost §7).

## 5 · Provider-agnostic model matrix — what's actually needed

Short answer to "do we need new ports/adapters architecture?": **no — the
seam already exists.** recurve's loop contract is: *an agent is any command
that reads a cycle prompt on stdin and writes a run-record to
`$RECURVE_RESULT_FILE`* (`$AGENT_CMD` / `recurve run --agent`). Providers
plug in as thin adapter scripts; the engine never learns who it's talking to.

What each provider needs is a ~50-line wrapper conforming to that contract:

| Provider/model | Adapter | Notes |
|---|---|---|
| Anthropic (Fable, Opus 4.8, Sonnet) | `claude -p --bare --permission-mode bypassPermissions` | exists today; `--bare` avoids hook interference |
| OpenAI (GPT-5.x, codex-style) | codex CLI if available, else a driver script (API: prompt in, tool-use loop, patch out) | driver script ~1 day |
| Google (Gemini) | gemini CLI or driver script | same shape |
| Open models (Qwen-coder, DeepSeek) | vllm/ollama + the same driver script | driver is shared; only the endpoint differs |

**What IS missing** (small, real): a **telemetry normalization layer** — the
run-record schema already has a `tokens` object; the adapters must populate
it uniformly (prompt/completion/total + provider list price → cost). One
shared `bench/adapters/telemetry.py` + a per-provider price table, pinned by
date. Plus per-adapter: version pinning (model string recorded verbatim),
timeout policy, and a retry contract (retries count as attempts — they're
part of the cost story, never silently absorbed).

## 6 · Pipeline architecture

```mermaid
flowchart LR
  TS[TaskStore\npinned benchmark revisions] --> WF[WorkspaceFactory\ndocker or worktree per run\noracle stripped OUT]
  AM[ArmComposer\nrecurve.toml + flags per arm] --> WF
  WF --> RUN[Runner\nAGENT_CMD adapter x budget cap]
  RUN --> DONE{agent declares done\nor budget exhausted}
  DONE --> OQ[Oracle Quarantine\nheld-out tests applied\nin a SEPARATE container]
  RUN --> REC[(run records + receipts\nper-run JSONL)]
  OQ --> RES[(results.jsonl\none row per task x arm x model x budget)]
  REC --> RES
  RES --> AN[Analysis\npaired stats, CIs, curves, tables]
```

Components (each a claim suite in the bench target):

1. **TaskStore** — downloads + pins benchmark instances (HF `datasets` /
   git clones at fixed revisions); materializes a task as `(repo state,
   task statement, oracle bundle)`. The oracle bundle is stored *outside*
   the workspace from the start.
2. **WorkspaceFactory** — one isolated workspace per (task, arm, model,
   budget, seed): docker for SWE-bench (their official images), git
   worktrees + venvs for lighter tiers. **The workspace never contains the
   held-out oracle** — this is the load-bearing isolation. For gate arms it
   also stamps the arm's `recurve.toml`.
3. **ArmComposer** — the ablation matrix → concrete configs (§4). Pure
   function; the arm identifier in every results row reproduces the config.
4. **Runner** — launches the provider adapter under a token/wall-clock
   budget; for recurve arms the agent works the claim loop (it authors
   claims/probes from the task statement — which also exercises §7.4
   automated-authoring honestly); for control arms it just works the task.
   Emits run-records + receipts.
5. **Oracle Quarantine** — after the run *ends*, a separate container mounts
   the final workspace read-only, injects the held-out tests, runs them, and
   emits the oracle verdict. The agent process is dead before the oracle
   exists anywhere near the workspace. (Threat: oracle leakage via model
   memorization of the benchmark — that's the LiveCodeBench sensitivity arm,
   not something quarantine can fix.)
6. **ResultsStore** — one JSONL row per run:
   `{task, benchmark_rev, arm, model, model_version, budget, seed,
   declared_done, oracle_pass, gate_verdicts, attempts, rejections,
   tokens{...}, cost_usd, wall_s, recurve_commit, receipts[...]}` —
   deterministic, diffable, and **exportable through `recurve trajectories`**
   so the evaluation corpus is itself provenance-gated.
7. **Analysis** — a small, boring, pinned script set (not notebooks-as-truth):
   paired McNemar tables, Wilson CIs, `pass@budget` curves, the confusion
   matrix table, price-of-trust table. Every figure in the paper regenerates
   from `results.jsonl` by one command.

**Where it lives:** `bench/` in the recurve repo as its **own uv project**
(`bench/pyproject.toml` with `datasets`, `docker` SDK etc.) — the engine's
stdlib+PyYAML posture is untouched because `recurvelib` never imports bench.
The bench is a recurve *target* (own suite in the ledger): the TaskStore
pinning, quarantine isolation, telemetry normalization, and analysis
determinism are all claims with traps (e.g. trap: a workspace that *does*
contain the oracle file must be refused by the factory).

## 7 · Experimental designs, per metric family

**E1 — Interception (M1): synthetic + real defects.**
Substrate: BugsInPy (real) + mutmut mutants (volume) over 3–5 pinned Python
repos with recurve suites authored once (by us, gated). For each defect:
apply, run gate per layer-arm (A2→A4), record block/pass. Output: the
per-layer confusion matrix + marginal detection + trap-count and fuzz_n
efficacy curves. No LLM in the loop → cheap, high-volume, fully
reproducible. *This is the first table the paper gains.*

**E2 — The A/B (M2): false-done rate under held-out oracles.**
Substrate: SWE-bench Verified subset (start n=50 stratified by difficulty;
scale to 200+ for the venue version) × arms {A0, A1, A3} × models {Sonnet,
GPT-5.x-equivalent, one open model} × one budget tier. Headline: ΔFDR and
oracle-pass@budget with CIs; secondary: gate-rejection rate, price of trust.
Pilot on SWE-bench Lite n=20 first to burn in the pipeline.

**E3 — Scaling/cost curves.** E2's A0 vs A3 rerun across a budget grid
(e.g. 200k/500k/1M/2M tokens) on a fixed n=30 subset → `pass@budget` and
`verified-pass@budget` curves. The question the curve answers: does the
gate's overhead ever stop paying for itself as budget grows?

**E4 — Model matrix.** E2's A3 arm across the provider matrix — the
framework's value *as a function of the agent's strength* (hypothesis worth
testing honestly: the gate's ΔFDR is *largest* for weaker/cheaper models,
which is the economic argument for gate+cheap-model vs bare+frontier-model).

**E5 — Decorrelation (the §2.9 residue).** Over E1's defect corpus: actor
authors a fix, adversary reviews via the capture rule; measure
miss-correlation ρ for same-model vs cross-model actor/adversary pairs.

**E6 — Strong-oracle track.** miniF2F subset with Lean-kernel probes (the
navier-style probe engine generalizes): the same A0-vs-A3 design where the
oracle is sound — measures the oracle-spectrum thesis instead of assuming
it (prediction: FDR(A0) is *high* even here — models claim proofs they
don't have — but gate FPR≈0, so ΔFDR is nearly pure gain).

## 8 · Threats to validity (and the mitigation built into the design)

- **Oracle leakage into the workspace** → quarantine architecture (§6.5);
  plus a trap: a planted workspace containing the oracle must be refused.
- **Benchmark contamination** (models memorized SWE-bench) → LiveCodeBench
  sensitivity arm; report headline effects on both; if the effect only
  exists on pre-cutoff tasks, say so.
- **Flaky oracles** → SWE-bench *Verified* exists precisely for this; for
  BugsInPy, 3× oracle re-runs, majority verdict, flake rate reported.
- **Arm cross-talk** (agent in A0 benefiting from recurve artifacts) →
  fresh workspace per run; arms never share state.
- **Cherry-picked tasks** → task subsets selected by pinned seed, published
  in results.jsonl before runs (registered-report style).
- **Our own bias** — the harness is recurve-gated, and the analysis scripts
  are deterministic and re-runnable from published results.jsonl: the same
  "reproduce our numbers without trusting us" affordance the paper needs.

## 9 · Phasing, cost, and what each phase feeds the paper

| Phase | Builds | Cost (rough) | Paper payoff |
|---|---|---|---|
| P0 (days) | bench/ skeleton, TaskStore + quarantine + telemetry claims, HumanEval+ smoke (n=20, A0 vs A3, one model) | ~$50–150 API | pipeline exists; §5 gains "the harness" |
| P1 (days–week) | E1 interception: BugsInPy + mutmut, layer arms A2–A4 | CPU only | **the confusion-matrix + ablation table** — the single biggest metrics upgrade |
| P2 (week+) | E2 pilot (Lite n=20) then Verified n=50, 3 arms × 2–3 models; E3 budget grid on subset | ~$1–5k API | **ΔFDR headline + price-of-trust + scaling curve** |
| P3 (opportunistic) | E4 model matrix, E5 decorrelation, LiveCodeBench sensitivity | ~$1–3k | ablations complete; residue #3 measured |
| P4 (later) | E6 strong-oracle track (miniF2F) | Lean infra reuse | oracle-spectrum thesis measured, not asserted |

Everything through P1 has **no meaningful API cost** and already produces
the table that answers "your metrics aren't that great." P2 is where money
meets the headline number.

## 10 · Build plan / PRD-ization

This document decomposes into two PRDs, both admissible in the usual form:

- **PRD-EVAL-1 (P0+P1):** bench skeleton + the three to-build ablation
  switches (boundary-off flag, single-context runner mode, controller-off
  runner mode — each engine/harness knob a claim with a trap) + TaskStore
  pinning + quarantine + E1 end-to-end with the confusion-matrix table as a
  generated artifact. All CPU; fully gateable; the fixture-repo suites are
  authored once and reused.
- **PRD-EVAL-2 (P2+):** provider adapters (OpenAI/Gemini/open-model drivers
  + telemetry normalization), SWE-bench workspace factory (docker), E2/E3
  runs, analysis tables. Gateable except the spend itself, which is a budget
  decision (knob, not policy: `--budget` caps per arm).

First concrete steps if green-lit: write PRD-EVAL-1, `recurve admit` it,
author the bench suite claims RED-first, and let the loop build its own
measuring instrument.
