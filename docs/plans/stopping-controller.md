# Plan: the stopping controller — stop / revert / pivot, decided by measurement

> Status: design / proposed phase. Sits **on top of** `completeness-layer.md` (it reads the frontier and the
> fidelity gate as progress signals) and obeys `separation-of-refereeing.md` (the controller is a
> deterministic referee — never the actor). Greenfield, origin-agnostic.

---

## 0. The problem

Agents are bad at stopping. Three distinct decisions, all hard for them:

- **Good enough → stop and move on.** (terminate-success)
- **Fundamentally wrong → stop and revert.** (terminate-failure)
- **Change direction → keep going, on a different part.** (re-allocate)

The reason is one thing: an agent has **no stable referent for "done."** Left to self-assess, it optimizes
the objective it was trained on — *produce something that looks complete* — not *satisfy a measurable
target*. So it declares victory early (trained to wrap up) or thrashes (it cannot tell progress from motion).
"Am I done?" answered by the actor is a vibe, and vibes do not converge.

**The reframe: stopping is not a reinforcement-learning problem — it is a control problem, and it only
becomes solvable once "done" is measurable.** recurve already makes "done" measurable (the gate). Given a
measurable objective, stopping reduces to **classical sequential-stopping rules** — stop when the objective
clears a threshold, abandon when the iterate stops improving, re-allocate when another arm looks better.
recurve supplies the objective the agent lacks; this controller applies the rules.

The architectural move (this is `separation-of-refereeing.md` applied to stopping): **the actor makes
changes; a deterministic controller decides stop / revert / pivot by reading measured progress against the
contract.** The actor never decides when to stop — it has the wrong incentive *and* cannot distinguish
progress from motion. Don't ask the agent if it's done; **measure it.**

---

## 1. Principles (continuous with recurve)

- **Measurement over judgment.** The stop decision is *read from* measured progress, never asserted by the
  actor. It is the "controller" row of the referee hierarchy — deterministic, and not an agent at all where
  it can be avoided.
- **Totality.** Every cycle yields exactly one controller verdict —
  `CONTINUE / STOP-SUCCESS / STOP-REVERT(→baseline) / PIVOT(→claim)` — the way a probe yields exactly one
  exit code. No ambiguous "maybe keep going."
- **Monotone, extended to effort.** The gate already never un-proves a claim. The controller adds: never
  *thrash* unboundedly (bounded non-progress forces a verdict) and always work the highest-value open item.
- **Honest revert.** `STOP-REVERT` quotes the evidence — the flat progress curve, the persistent divergence —
  not a guess, and it names the cycle it reverts to.
- **Built on a faithful contract.** You cannot measure progress toward "done" if "done" (completeness +
  fidelity, `completeness-layer.md`) is undefined. This controller inherits the contract's quality (§7, §8).

---

## 2. The progress vector (what the controller reads each cycle)

recurve already records measured state per cycle (the ledger / promotion records). The controller consumes a
per-cycle **progress vector**, every field *measured* from the gate, the coverage map, and the ledger —
nothing asserted:

| field | source | reads progress toward… |
|---|---|---|
| claims `closed / open` | the gate | soundness |
| claims `regressed` (was GREEN, now RED) | the gate vs. prior cycle | thrashing |
| claims `BROKEN` | the gate | un-measurability |
| frontier `size` + `Δ` | the coverage map | completeness |
| coverage `covered(strong/weak) / uncovered / deferred / unmeasurable` | the coverage map | completeness |
| `divergent?` (a goal-counterexample passes) | the fidelity gate | intent |
| `effort` (cycles spent, changes made) | the ledger | the denominator for *progress per effort* |

The vector is the controller's only input. The actor produces changes; it does not produce this vector.

---

## 3. The verdict state machine

Each cycle, after the gate runs, the controller emits exactly one verdict:

### `STOP-SUCCESS` — the threshold-stop (good enough)
The gate is GREEN (soundness ∧ completeness ∧ fidelity) **and** the `deferred` set is within policy (the
explicit deferrals are acceptable to the contract / the human). "Good enough" is therefore not a vibe — it
is *"the must-haves are covered and the rest is explicitly, acceptably deferred."*

### `STOP-REVERT(→baseline)` — non-improvement / divergence (fundamentally wrong)
The approach is not converging. Fired by **any** of:
- **Persistent divergence** — `divergent?` stays true over *k* cycles: the work keeps satisfying the letter
  while a goal-counterexample keeps passing. The approach is solving the wrong problem.
- **Thrashing** — the claim-`regressed` rate stays high over *k* cycles: closing claims keeps breaking closed
  ones. The approach is fighting itself.
- **Flat progress** — `open + frontier` is not net-shrinking over *k* cycles *despite changes being made*.
  Stuck.
- **Irreducible un-measurability** — `unmeasurable` surface/claims that cannot be made measurable under this
  approach. It can't even be evaluated.

The revert **target** is the last cycle in the ledger where the gate was GREEN (or the initial baseline if
none) — it exists and is named (§5). The verdict carries its evidence.

### `PIVOT(→claim)` — re-allocation (change direction)
Keep working, but switch the active item. Fired when the current item's *progress-per-cycle* has stalled
**and** another open claim / frontier point has higher *expected value × tractability*. Re-rank the open work
(a lightweight bandit over the frontier, ranked by each point's `weight`) and switch to the best arm.

### `CONTINUE`
None of the above — keep working the current item.

> **Ordering matters: try `PIVOT` before `STOP-REVERT`.** A stalled *item* is not a dead *approach*. Exhaust
> re-prioritization (is there a more tractable open item?) before concluding the whole approach is wrong.
> Revert is the heavy verdict; reach it only when re-allocation can't find progress either.

---

## 4. The thresholds — parameters first, learned later

The rules depend on a few parameters: *k* (cycles of non-progress before reverting), what counts as
"stalled" (progress-per-cycle below ε), and the bandit's value estimates.

- **Start with explicit heuristics** (e.g. *k = 3* flat cycles → revert; "stalled" = 0 frontier-progress for
  2 cycles → pivot). Simple, legible, debuggable.
- **Only then calibrate them — from recurve's own ledger.** recurve accumulates measured histories: how often
  did a "flat" plateau break through on the next cycle vs. stay stuck? That *is* the training signal for the
  thresholds. Keep any learned component **interpretable** (a calibrated number / a readable value estimate),
  never a black-box policy (§6).

---

## 5. Revert-to-baseline mechanics

- recurve's monotone ledger records each cycle's measured state and its work artifact, so the **last-GREEN
  cycle is a named target** — no guessing what to revert to.
- Revert is **not** "delete everything." The **contract survives** (it is the spec); only the failed
  *implementation attempt* is discarded, and the work returns to the last green cycle to be re-posed.
- The receipt records **why** (the divergence/flat-progress evidence) so a re-attempt does not re-enter the
  same dead end; optionally the failed approach is kept as a negative-result note ("this approach diverged on
  X") to inform the next.
- **Revert-loop guard.** If the same approach reverts repeatedly, the controller escalates to the human — its
  honesty extends to *"I cannot find a converging approach; your contract may be infeasible or unfaithful."*
  It does not loop forever.

---

## 6. Is this reinforcement learning? (the honest boundary)

**Mostly no — and reaching for RL here is the mistake.** Given a measurable objective, stopping is a
*classical* sequential-stopping / control problem (threshold-stop, non-improvement detection, bandit
scheduling), not a policy-learning problem.

- **Deep RL is the wrong tool:** sample-hungry, opaque — you cannot ship *"the model felt done"* in a trust
  tool — and unnecessary when you already have an engineered reward (the gate) and structure (the contract +
  frontier).
- **The only place learning belongs:** lightweight, *interpretable*, online calibration of (a) the abandon
  thresholds (case 2's genuine explore/exploit tension) and (b) the bandit value estimates (case 3) —
  learned from the measured ledger. Engineered controller first; calibrated thresholds later; never a black
  box.

The contribution is the conversion itself: **recurve turns stopping from a policy-learning problem (RL) into
a stopping-rule problem (sequential analysis) by supplying the measurable objective the agent lacks.**

---

## 7. Binding to the other invariants

- **`separation-of-refereeing.md`:** the controller is the deterministic "controller" row of the referee
  hierarchy. The actor proposes changes and never decides stop/revert/pivot. The stop decision cannot be
  gamed by the actor because it is read from the gate — which the actor also does not referee. No agent
  judges its own doneness.
- **`completeness-layer.md`:** the progress vector's completeness fields (frontier, coverage) and its
  fidelity field (`divergent?`) come straight from the coverage gate and the goal-counterexamples. This
  controller **cannot function without them** — without completeness and fidelity defined, "progress toward
  done" is unmeasurable, and you are back to the actor guessing. So this doc sits strictly *on top of* the
  completeness layer.

---

## 8. Honest limits

- **Garbage contract → confident wrong stop.** If the contract is an unfaithful proxy for intent, the gate
  goes GREEN on the wrong thing and `STOP-SUCCESS` fires wrongly. The controller inherits the contract's
  quality; the completeness/fidelity layer is the prerequisite, not optional.
- **Revert (case 2) is genuinely hard.** The explore/exploit tension is real: abandon too early and you kill
  a plateau about to break; too late and you thrash. The measurable progress signal makes it *tractable*, not
  *easy* — this is where calibration earns its keep, and escalate-to-human is the safety valve.
- **Pivot (case 3) cold-starts weak.** The expected value of an *unopened* claim is uncertain; lean on the
  human-supplied `weight` on the frontier until the ledger has history to estimate from.
- **It cannot rescue an infeasible goal.** If no approach converges, the honest output is "your contract may
  be infeasible/unfaithful," escalated — not infinite trying. The controller's job is to *stop*, including
  stopping the search itself.

---

## 9. Build order

Sequenced so the highest-value verdicts land first:

- **P1 — progress vector (read-only).** Record and display per-cycle progress from the gate + frontier.
  Makes "are we actually making progress?" visible before any automatic verdict.
- **P2 — `STOP-SUCCESS` + simple `STOP-REVERT`.** Threshold-stop on green; revert on the simplest signal
  (flat progress over *k* cycles) with revert-to-last-green. The two highest-value verdicts.
- **P3 — `PIVOT`.** The bandit over the frontier — re-prioritization within a converging approach.
- **P4 — divergence/thrashing reverts.** Needs the fidelity gate + regression tracking from the completeness
  layer.
- **P5 — threshold calibration** from the ledger (interpretable). Optional, last.

---

## 10. The receipt

A stopped cycle's receipt records the controller's verdict **and its evidence**: GREEN (the gate), or
reverted (the flat-progress / divergence evidence + the baseline reverted to), or the pivot trail. Honest by
construction — the receipt says not just *"done"* but *"stopped because [measured reason]."*

---

**One line:** stopping is a control problem, not an RL problem — it becomes solvable the moment "done" is
measurable, which recurve provides. The actor keeps making changes; the controller, watching the gate,
decides — by measurement, never by the actor's say-so — when to stop, revert, or pivot.
