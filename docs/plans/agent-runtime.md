# Agent runtime: the autonomous burndown loop

## 0. What this is, and what it is not

recurve today is a tool a human drives: you author claims, run `matrix --gate`, read the frontier, make a
change, re-gate. Everything built around it so far — surface extraction, measured coverage, the completeness
gate, fidelity, the stopping controller — is a **sensor** or a **judge**. None of them *act*. This layer is
the **loop that closes around them**: hand it a reviewed contract and it burns the contract down on its own —
choosing what to work, making the change, measuring the result, deciding when to stop or revert — without
ever trusting its own report that it is done.

It is **not** a new agent, and not a smarter one. recurve stays BYO-agent: the *actor* is any coding agent
you plug in. What this layer adds is the deterministic **spine** that makes a non-deterministic actor *safe
to leave alone*: it measures instead of believing, stops instead of looping, reverts instead of shipping, and
is checked by a separate adversary it cannot influence. The trust comes from the spine, never from the actor.

## 1. The cycle

One cycle is five phases, in order. Only **Act** runs an actor; everything else is deterministic or a
separate, decorrelated agent.

1. **Sense** — measure the world; never ask the actor how it went.
   - The gate: every claim's probe → `{open, closed, regressed, broken}` (the existing `probe`/`matrix`).
   - Completeness: `surface.extract_surface` → `measured.measure_coverage` → `frontier.compute_frontier` →
     the ranked uncovered set.
   - Fidelity: the goal-counterexamples → `fidelity.divergent`.
   - Assemble the `controller.Progress` vector from these — all measured, none asserted.
2. **Decide** — deterministic, by the controller.
   - `decide(history)` → `CONTINUE` / `STOP-SUCCESS` / `STOP-REVERT`.
   - `pick_next(frontier, current, stalled)` → the next item, and `PIVOT` when a stalled item is outranked.
3. **Act** — the only phase with an actor.
   - `CONTINUE`/`PIVOT`: hand the actor the contract + the one chosen item + the failing probe evidence; it
     returns **one smallest change** (a diff) to the **target tree only**.
   - `STOP-REVERT`: restore the last gate-certified-green state from the monotone ledger; the actor is not
     called.
   - `STOP-SUCCESS`: halt; emit the receipt.
4. **Referee** — never the actor.
   - Correctness and stopping were already judged deterministically in Sense and Decide.
   - **Adversary (periodic):** a separate agent red-teams the new/changed claims and tries to find a wrong
     implementation that still passes them. Findings become traps — the **capture rule** — so a one-time
     objection becomes permanent, re-runnable evidence. Its context is never shared with the actor.
5. **Record** — append to the monotone ledger; the baseline ceremony promotes only what was *measured*
   GREEN. Hash-chained receipts make the whole run auditable after the fact.

The loop repeats until Decide returns a STOP or the human gate is invoked.

## 2. The roles, and the wall between them

| Role | Who | Decides | May write |
|---|---|---|---|
| **Actor** | a coding agent (BYO, pluggable) | nothing | the **target tree only** |
| **Probe referee** | deterministic (`probe`) | each claim GREEN/RED/BROKEN | nothing |
| **Controller** | deterministic (`controller`) | CONTINUE/STOP/REVERT/PIVOT | nothing |
| **Adversary** | a separate agent (decorrelated) | "this claim is incomplete" | proposes traps (then gated) |
| **Human gate** | the person | approves the contract; takes escalations | claims, contract, ceiling |

The separation-of-refereeing invariant — *an actor never referees its own work* — is enforced here as a
**write boundary**, the single most important safety property of the loop:

- The **actor writes only the target tree.** It may not write claims, probes, traps, the ledger, or the gate
  config.
- If the actor could weaken a probe to make it pass, the gate would certify nothing — the "agent grading its
  own homework" failure, at the infrastructure level. The boundary makes that **structurally impossible**:
  the referee surface is read-only to the actor.
- Only the **human** (authoring/curating the contract) and the **adversary** (via the capture rule) may
  change the referee surface — and an adversary's proposed trap counts only once it is seen RED against the
  current tree. The referee can only ever get *stricter*, never weaker, and never by the hand that's being
  graded.

## 3. The runtime interface (BYO-agent)

What the runtime hands the actor each Act:

- the **contract** — the claims in scope, human-approved;
- the **one item** to work (a frontier point or an open claim) — never "fix everything";
- the **failing evidence** — the probe's `ours= / oracle=` output;
- the **write boundary** — the target paths it may touch.

What it expects back: a **diff** against the target tree. Nothing else — no "I'm done," no self-assessment.
**The actor's word is never an input to a verdict.** This is *measurements, not intentions* made operational:
the runtime re-measures from scratch every Sense, so a confident-but-wrong actor cannot advance the loop.

recurve already ships BYO-agent burndown templates (`templates/workflows/`). This layer turns that *open*
scaffold into a *closed* loop by adding Decide, the completeness Sense, the adversary turn, and the write
boundary. It is orchestration over existing primitives, not a rewrite.

## 4. Invariants the runtime must hold (the claims for this layer)

What a future `claims/runtime` suite would gate — each with its kept counterexample:

- **Self-report is never trusted.** A cycle's verdict is a pure function of the measured Progress vector; the
  actor's output influences only the diff. *Trap:* a runtime that stops because the actor said "done" while
  the gate is still RED.
- **Monotone safety.** A closed claim never silently reopens; STOP-REVERT restores the last green floor.
  *Trap:* a revert that leaves a regressed claim marked closed.
- **Termination.** Every run halts — STOP-SUCCESS, STOP-REVERT to a green floor, or a human escalation; it
  cannot loop forever. (Guaranteed by the controller.) *Trap:* a Progress history continued past the revert
  thresholds.
- **The write boundary holds.** A cycle whose diff touches the referee surface is rejected, not gated.
  *Trap:* an actor diff that edits a probe or a claim.
- **Bounded blast radius.** Each cycle is one smallest change, gated and individually revertible. *Trap:* a
  cycle that batches changes so a revert cannot isolate the bad one.
- **Escalation, not thrash.** Repeated STOP-REVERT on the same contract escalates "this contract may be
  infeasible or unfaithful" to the human instead of retrying forever (stopping-controller's revert-loop
  guard). *Trap:* an Nth identical revert that silently retries.

## 5. Build order

Sequenced so a *safe* loop runs before a *smart* one:

- **A1 — the minimal closed loop.** Sense (existing gate only) → `decide` → Act → revert-to-last-green. No
  completeness, no adversary. This alone is an autonomous RED-claim burndown, safe because of the gate +
  revert. The honest MVP.
- **A2 — completeness Sense.** Wire surface/coverage/frontier into Sense so `pick_next` ranks real uncovered
  work; the loop now closes silent holes, not just RED claims.
- **A3 — fidelity Sense.** Feed `divergent` so the loop refuses a success-stop on a goal-counterexample.
- **A4 — the write boundary.** Enforce that actor diffs touch only the target tree; reject otherwise. *Land
  this before A5* — an autonomous actor without the boundary can game the gate.
- **A5 — the adversary turn.** A periodic separate agent red-teams new claims; the capture rule turns
  findings into traps. The loop now hardens its own contract (as this very build did, by hand, three times).
- **A6 — the human gate + the actor adapter.** Contract approval before burndown; escalations out; a
  reference actor adapter behind a stable interface so the actor is swappable.

A1 is shippable on its own: an autonomous loop you can trust *because the trust lives in the deterministic
spine, not the actor*.

## 6. Honest limits

- **The actor can be wrong, often.** The loop's safety is the gate + revert + the write boundary, never the
  actor's competence. A weaker actor makes the loop slower, not unsafe.
- **The adversary is an LLM too.** It reduces blind spots; it does not eliminate them — it found 14 holes in
  this build and surely missed some. The human gate is the backstop, not an optional step.
- **Cost is a first-class failure mode.** Each cycle spawns agents and re-measures; an autonomous loop with
  no budget ceiling will burn money on diminishing returns. The human sets the ceiling; the loop respects it.
- **A contract with too few invariants cannot be gated** (completeness-layer §7). The loop must *detect* that
  and refuse to run autonomously — handing back to the human — rather than burning down a brittle proxy.
- **Garbage contract in, garbage burndown out.** The loop faithfully achieves whatever the contract says.
  Fidelity catches *some* drift from intent (goal-counterexamples), not all. The human-approved contract is
  load-bearing; this layer does not relieve the human of authoring a faithful one — it relieves them of
  *driving the burndown*.

## 7. How it composes with what is built

```
   target tree ──▶ Sense ───────────────────────────────▶ Progress
                    │  surface→measured→frontier  (completeness)
                    │  probes                     (the gate)
                    │  goal-counterexamples→divergent (fidelity)
                    ▼
                 Decide  ── decide() / pick_next()  (controller)
                    ▼
   CONTINUE/PIVOT ─▶ Act (actor: one diff, target tree only) ─▶ Record ─▶ ledger
   STOP-REVERT ───▶ restore last green ────────────────────────▶ Record
   STOP-SUCCESS ──▶ receipt + halt
                    ▲
                 Adversary (periodic, separate) ──▶ new traps  (capture rule)
```

Every sensor and judge this layer needs already exists and is itself gated: `frontier`, `surface`,
`measured`, `completeness`, `fidelity`, `controller`, plus the gate, ledger, baseline ceremony, traps, and
BYO-agent templates. This layer is **orchestration plus exactly one new safety primitive — the write
boundary.** That is why it is the right next scope: the hard, gateable parts are done; what remains is the
runtime that lets them run themselves, safely.
