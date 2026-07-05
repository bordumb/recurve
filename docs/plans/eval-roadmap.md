# Eval roadmap — POC → ablation → long time horizon

> Sequencing only. For the *what*/*why* of each experiment's design, see
> `eval-poc.md` (the core POC), `eval-full.md` (arm matrix, E1–E6), and
> `oracle-strength-and-decorrelation.md`/`ablation-infra.md` (the
> adversary/governor mechanisms this ablates). The `eval/` pipeline and the
> governance mechanisms are built and gated (`main`, PR #14) — this doc is
> about what to *run*, in what order, and how to know each phase is done.

## Ablation — the full matrix, and what to run first

**Everything recurve can currently switch off, independently:**

| Switch | Values | What it isolates |
|---|---|---|
| `[gate] traps` | on / off | RED-first enforcement itself |
| `drill --fuzz` | on / off | probe false-positive measurement |
| `drill --iso` | on / off | isomorphic trap generation |
| `drill --diff` | on / off | differential check against a reference |
| Write boundary | on / off | can the actor touch the referee surface |
| Controller | on / off | external stopping vs. trusting the agent's "done" |
| `[gate] adversary` | off / same_model / cross_model | per-claim decorrelation |
| `[gate] governor` | off / mechanical / mechanical_review / human_required | run-level decorrelation |

These compose into `eval-full.md`'s arm ladder (not a factorial — see that
doc's §3a for why):

```
A0 no-recurve · A1 plain-CI · A2 claims+probes, traps off · A3 full discipline
A4 A3+fuzz/iso/diff · A5 A3, boundary off · A6 A3, controller off
A7 A3+adversary=cross_model · A8 A3+governor=mechanical
A9 A3+governor=mechanical_review · A10 A3+adversary+governor (full stack)
```

**Where this is actually maintained.** `eval-full.md`'s table above is the
*documented* superset, with the rationale for each arm. The *runnable*
source of truth is code: `eval/evallib/arms.py`'s `_ARMS` dict — a pure
name → workspace-spec mapping (`recurve: bool`, `config: dict`, `label:
str`), resolving `adversary=`/`governor=` through `recurvelib.adapters`'
own registry rather than reimplementing anything (`ablation-infra.md`
AI5). Adding an arm is one dict entry there, never new logic.

**Update (`eval-arm-kernel.md`):** `_ARMS` now holds `ArmSpec` tuples (one
field per port — workspace/done_signal/boundary/audit/adversary/governor),
not the flat `{"recurve", "config"}` dict described above, and `A4`, `A5`,
`A6` are now real, runnable entries (`A6` shares `A0`'s `self_report`
done-signal port; `A5` uses the new, real, off-by-default `BoundaryPort`;
`A4` uses the new, additive-only `AuditPort`). `A1`/`A2` still have no
entry — `A2` is a separate, pre-existing axis (`[gate] traps`) outside this
port set, and `A1` is still blocked on the design question below.

**As of the original writing, only `A0`, `A3`, `A7`, `A8`, `A9`, `A10` existed
in that dict.** `A1`, `A2`, `A4`, `A5`, `A6` were documented in `eval-full.md`
but had no `arms.py` entry yet. That was not a coincidence with the "run
first" list below: the initial set was exactly the subset already wired to
run.

**What to run initially: A0, A3, A7, A8, A9, A10.** These answer the two
questions we actually have live, unanswered stakes in right now — the
headline effect (A0 vs A3) and the decorrelation payoff (A7–A10, which is
what turns the O6 incident from an n=1 anecdote into a measured rate.
**Deferred, not dropped**: A1 (a weaker control than A0), A4 (hardening
margin — a different question), A5/A6 (leave-one-out on older, already-
trusted mechanisms). Revisit these once A0/A3/A7–A10 have real numbers.

---

## Phase 1 — The core POC (A0 vs A3)

**What / unlocks / why.** The headline effect size: does the gate reduce
shipped-bad-work at matched budget, across Haiku 4.5 and Sonnet 5, on
BigCodeBench-Hard. Unlocks the paper's first real table and validates the
harness at actual scale — everything so far is a 1-task, $2 smoke.

**Tasks remaining.**
- `eval plan` on the current manifest (`n=50` pilot) — review `matrix.jsonl`
  and the cost estimate before any spend.
- `eval run` the pilot → `eval analyze`; check the process-failure split
  first (Haiku's A3 cells specifically) — one prompt/skill iteration if
  harness-operation failures dominate over task failures, otherwise proceed.
- Flip `sample` to the full 148 tasks, re-run.
- `eval analyze` on the full run.

**Done when.** ΔFDR computed with paired McNemar + Wilson 95% CIs at
n=148, compared against the pre-registered guesses already committed in
`eval-poc.md` §8 (matching *or* diverging both count — either is reportable).
No cell hit the hard-kill watchdog unexpectedly; if one did, that's a
finding to explain before trusting the rest of the run.

---

## Phase 2 — The ablation ladder (A7–A10)

**What / unlocks / why.** Marginal value of decorrelation, per mechanism:
does cross-model adversary alone help, does the free mechanical-governor
tier alone help, does mechanical-review alone help, does the full stack
beat any single piece. This is E5's decorrelation study getting real
numbers instead of the O6 anecdote, and it's the direct empirical test of
everything `oracle-strength-and-decorrelation.md`/`ablation-infra.md` built.

**Tasks remaining.**
- Extend the manifest with arms A7–A10 (already defined; no new engine
  work — this is pure config, resolved through the registry both PRDs
  built).
- Run on the same pinned task set Phase 1 used (reuse the n=50 pilot
  first, since the pipeline is already warm; scale to 148 only if the
  pilot's numbers look worth the spend).
- Build the paired table: for every task A3 shipped bad, did A7/A8/A9/A10
  fix it, refuse, or also ship bad (mirrors the O6 incident's own
  breakdown, at n≫1 this time).

**Done when.** A per-arm marginal-detection table exists (A7 vs A3, A8 vs
A3, A9 vs A3, A10 vs A3), with a miss-correlation ρ computed for the
adversary tiers if the data supports it. A10 either does or doesn't beat
its components alone — both outcomes are the actual result, not a target
to hit.

---

## Phase 3 — Long time horizon

**What / unlocks / why.** One distinction first: SWE-bench Verified (E2)
is more *realistic* (real repos) but still a single-issue fix, typically
under an hour — not actually long-horizon. The genuinely long-horizon case
is what recurve is actually built for — multi-hour, multi-file, drift-
over-time work, like the session that built `ablation-infra.md` itself.
That case has an unsolved problem: recurve's own ledger can't grade a run
gated by that same ledger without circularity. Start with the cheapest
possible test of an approach, not the most expensive.

**Tasks remaining.**
- Design the retrospective case-study protocol: a fresh, decorrelated
  reviewer gets only the original PRD text (`ablation-infra.md` as
  written) and the final diff — never this session's history or reasoning
  — and judges whether AI1–AI11 were satisfied non-vacuously.
- Run it once, against the artifact that already exists (zero new
  building required to attempt this).
- Based on what it finds, decide the next investment: harden the same
  adversarial-review approach, or build the heavier held-out-acceptance-
  criteria design (redacting part of a PRD before a run, mirroring
  BigCodeBench's hidden-test pattern at PRD scale).
- SWE-bench Verified (E2) can proceed in parallel any time — it doesn't
  block on this, and it doesn't depend on solving the circularity problem.

**Done when.** The case study produces a verdict on `ablation-infra.md`'s
own build — either it agrees with the gate's original judgment (weak
validation, still n=1, same caveat as O6) or it finds something the gate
missed (strong evidence the approach is worth investing in further). Either
outcome determines the next design decision; neither is a failure.
