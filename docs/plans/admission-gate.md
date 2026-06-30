# The admission gate: is this goal even gateable?

## 0. Why this is Layer 0

Every other layer assumes a *contract* already exists — a set of claims worth burning down. But a human does
not arrive with a contract; they arrive with a goal, and the goal is often vague: "make the loop robust,"
"build A1." The agent-runtime's honest limit is "garbage contract in, garbage burndown out." This layer
attacks that at the door instead of confessing it downstream: **before any synthesis or burndown, decide
whether the goal can be turned into a faithful contract at all — and if not, refuse, diagnose, and interview
the human until it can.**

It is the inversion of the garbage-in limit. Without it, a vague goal is silently burned down into a brittle
proxy and shipped green. With it, a vague goal is *caught*, its un-gateable parts named, and the human is
helped to make it gateable — or told honestly that it should not be gated at all.

This is also the answer to the oldest complaint about the tool: that it requires spoon-feeding. The admission
gate *does the spoon-feeding in reverse* — it interviews the human toward a good contract rather than failing
quietly on a bad one.

## 1. The question, made operational

The gate answers one question — **"is this goal gateable?"** — with a concrete, falsifiable definition, not a
rating:

> A goal is **gateable** to the degree each of its assertions is **probe-able**: you can name an executable
> check that would go **RED if the assertion were false.**

Gateability is therefore *measured*, the same way coverage is: count the assertions for which a falsifying
check can be named, against the total. A goal all of whose assertions are probe-able is admissible; one where
most are not is a wish, not a contract. The un-probeable assertions are not a verdict — they are the
**worklist for the interview.**

## 2. The rubric (each criterion is itself a check, not a vibe)

For the goal as a whole and each assertion in it:

- **Falsifiable** — there is an observable pass/fail. *"Make it robust"* fails this; *"a malformed input
  returns an error, never a crash"* passes.
- **Has a counterexample** — you can name what *wrong* looks like (the trap). An assertion with no
  conceivable counterexample is unfalsifiable and cannot be a claim.
- **Bounded scope** — the surface it touches is enumerable, so completeness is measurable. An unbounded goal
  ("handle all inputs") cannot have a frontier.
- **Enough invariants** — the goal is constrained by several stable, checkable properties, not one fuzzy
  aim. "Few invariants" is the signal of creative/exploratory work that should not be gated (§5).
- **Intent-anchored** — success is tied to what the human actually wants, with at least one
  *goal-counterexample*: a way the build could satisfy the letter and break the intent.

A criterion that fails is not "bad input." It is a precise, named gap.

## 3. The verdict: diagnostics, never a score

The gate emits one of three verdicts plus a falsifiable diagnostic list:

- **ADMIT** — every in-scope assertion is probe-able; hand off to synthesis (`completeness-layer.md §2`).
- **REFUSE-AND-INTERVIEW** — some assertions are not yet probe-able; emit the worklist and start the
  interview (§4). This is the common case and the productive one.
- **REFUSE-NOT-GATEABLE** — the goal has too few invariants to gate honestly (genuine exploration, taste,
  open design). Recommend *not* gating; say so plainly. Refusing to gate is sometimes the honest verdict.

The diagnostic is a list the human can verify item by item — *"`scope` is unbounded: 'all files' is not
enumerable; `assertion 3` has no oracle: 'fast enough' names no threshold; `assertion 5` has no
counterexample"* — never *"6/10."* A score hides the reasoning; a falsifiable diagnostic exposes it.

## 4. The interview (turning intent into claims)

For each un-probeable assertion, the gate asks the one question that makes it gateable:

> **"What would *wrong* look like here, concretely — and how would we see it?"**

That single question extracts the oracle and the counterexample at once. The interview is bounded by its own
stopping rule (it has the same problem the whole tool exists to solve):

- **Stop — admit** when every in-scope assertion has a named falsifying check.
- **Stop — escalate** when the human cannot name what *wrong* looks like after a bounded number of passes:
  that is the signal the goal is genuinely un-gateable (REFUSE-NOT-GATEABLE), not that the interview should
  continue forever.
- **Never** accept "it'll be obvious" as an oracle. An un-nameable check is an un-gated assertion.

The interviewer is a **separate agent** from the actor that will later do the burndown — the same
separation-of-refereeing invariant: the party assessing whether a contract is good must not be the party that
benefits from it passing.

## 5. Trust: why this is not just-another-LLM-judging

The gate's own verdict is falsifiable, which is what keeps it from being a vibe-check:

- "ADMIT" is checkable: it claims *every in-scope assertion has ≥1 executable probe*. If synthesis then fails
  to write a probe for some admitted assertion, the gate was wrong — and that is a detectable, recordable
  miss, not an opinion.
- The rater is separate from the actor, so a "pass" earns it nothing.
- The output is a diagnostic list, each item independently verifiable by the human.

The gate cannot be gamed by an actor (the actor never runs here), and it cannot quietly lower its own bar,
because its bar is "a probe exists," which either does or does not.

## 6. The boundary it does NOT cross (state this loudly)

The admission gate decides **gateable**, not **faithful**.

- It catches *vague* — a goal too loose to become claims.
- It does **not** catch *precise-but-wrong* — a crisp, fully-probe-able contract that does not match what the
  human meant. That contract sails through admission.

Faithfulness is still defended elsewhere and imperfectly: human curation of the proposed claims
(`completeness-layer §2`) and fidelity's goal-counterexamples at build time (`fidelity.py`). A human who
confidently approves a precise contract that misstates their intent is the one failure no layer removes. The
admission gate shrinks the garbage-in surface from "vague slop" to "only your own crisp mistakes" — a large
reduction, not elimination.

## 7. Build order

- **G1 — the rubric as a read-only report.** Given a goal, emit the per-assertion probe-ability diagnostic.
  No interview, no refusal — just the honest map of what is and isn't gateable. Shippable alone; it already
  ends silent garbage-in.
- **G2 — the three verdicts.** ADMIT / REFUSE-AND-INTERVIEW / REFUSE-NOT-GATEABLE, with the
  too-few-invariants detector for the last.
- **G3 — the interview loop.** The "what would wrong look like?" turn, with its convergence/escalation
  stopping rule; interviewer is a separate agent.
- **G4 — wire to synthesis.** ADMIT hands the now-gateable goal to the synthesis proposer; the loop is whole:
  admission → synthesis → human curation → burndown (agent-runtime).

## 8. Honest limits

- **The rater is an LLM.** It can misjudge probe-ability; G1's value is that its judgments are *falsifiable
  and recorded*, so misjudgments surface (an admitted assertion synthesis can't probe) rather than hide.
- **An over-strict gate blocks real work.** If it demands probes for genuinely creative goals, it becomes an
  obstacle. REFUSE-NOT-GATEABLE must be a real, easy verdict — "don't gate this" — not a failure state.
- **An interview that never converges is its own failure.** The stopping rule (§4) is load-bearing; without
  it the gate just relocates the thrash it was meant to prevent.
- **It cannot make a human know their own intent.** It can only force the intent to be *stated as checks*.
  If the human's stated checks are faithful, the contract is good; if not, see §6.

## 9. The gate, run on this very plan

By its own rubric, `agent-runtime.md`'s A1–A6 are **REFUSE-AND-INTERVIEW**: each names components but no
falsifiable done-condition and no counterexample. The honest output is the rewrite — e.g. *A1: "given a
one-claim RED contract and a stub actor emitting the fixing diff, the loop reaches STOP-SUCCESS in ≤N cycles,
the gate ends GREEN, the claim closes exactly once; counterexample it must reject — a stub whose diff edits a
probe is killed by the write boundary, not gated green"* — plus the interview for A2–A6. That a plan in this
same directory fails this gate, and is improved by it, is the demonstration.
