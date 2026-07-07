# PRD — the campaign orchestrator: automating the scope→work→rescope loop, safely

> Scope: a strategic-controller layer above the burndown loop that automates the
> *scope a decomposition → burn it down → analyze → rescope* cycle a human
> currently drives by hand — while keeping the human exactly where the map
> paper's §7.6 puts them: **accountability and taste, not correctness.** It
> composes mechanisms recurve already has (burndown, wave-arming, fansearch)
> under one controller, and adds the two pieces that are still manual: turning a
> goal into RED-first drafts, and choosing which campaign to run next. The design
> rule is one sentence — **automate what has an arbiter; checkpoint what does
> not** — and everything below follows from it.

> **Written pre-launch.** No deployments to preserve. This is additive
> orchestration; it changes nothing about how a single claim is certified.

## 0 · The loop today, and how much is already automated

The felt experience is a manual ping-pong:

1. human + loop scope a bounded slice into RED-first claims,
2. human says "work this slice,"
3. loop works it (triage → sculpt → gate → promote → commit → next),
4. loop empties the slice; human + loop scope the next,
5. repeat.

But steps 3 and much of 4 are **already automated**, and it is worth being exact
about it so a PRD targets the real gap, not a solved one:

- **`recurve next`** already reads the board and picks the highest-value open
  claim — the "when one completes, analyze the best next" step exists.
- **The burndown loop** already runs triage → work → gate → promote → commit →
  next, cycle after cycle, unattended, self-halting.
- **Wave-arming** already authors the next batch of claims from
  `gaps.draft.yaml` (probes + traps, RED-first, baselined) when the strict
  ledger empties, and continues.
- **fansearch** already *proposes* new candidate claims via an untrusted proxy
  and lets the gate confirm them (§3.5 of the framework).

So the automated substrate is substantial. Two things remain manual.

## 1 · The genuine gap: decomposition, and direction

- **Decomposition.** Turning a high-level goal — "prove R10," "build Sobolev
  spaces," "close the blowup side" — into the *content* of good RED-first drafts.
  Wave-arming arms drafts into claims, but the drafts' mathematical substance is
  seeded by a human PRD or an ad-hoc cycle. This is the framework's §7.4
  ("automated claim and probe authoring") made concrete.
- **Direction.** Choosing *which* campaign to build and run next — REG vs blowup
  vs the verified-numerics core vs the dyadic model; when to pivot; when a
  discovery search has said enough. `recurve next` ranks value *within* a ledger;
  it does not decide *which ledger to grow*. This is the framework's §7.1
  ("workflow and decomposition policies").

Both are LLM-automatable in principle — an agent *can* decompose and *can*
prioritize. The question is not capability. It is safety.

## 2 · Why the last mile is human-gated — the constraint any design must obey

Inside a claim, the Lean kernel is a sound arbiter: it says right or wrong, and
the whole framework's trust reduces to it. **The strategy and decomposition layer
has no such arbiter.** "Is this the right decomposition?" and "is this the best
next campaign?" have *no mechanical oracle* — they are taste. Two consequences
bound the design:

1. **Self-grading returns, one level up.** An agent that both *proposes* a
   decomposition and *scores* it is precisely the generator-grades-its-own-work
   failure recurve exists to prevent (the paper's "long-horizon LLM work fails at
   the judge, not the explorer"). Fully automate the closed loop and you have
   rebuilt the unrefereed generator at the strategy layer. The gate still catches
   a *false proof*; nothing mechanical catches a *misdirected decomposition* — it
   will dutifully burn cycles on a well-formed set of claims aimed at the wrong
   thing.
2. **Runaway spend.** A fully autonomous scope-and-burn loop has no resource
   checkpoint: it can decompose indefinitely and spend without bound. On a
   flat-rate consumer subscription (the map paper's §7.7) a single misdirected
   campaign can consume the month. Something must gate *resource commitment*, and
   only a human can be accountable for it.

The correct conclusion is not "keep it manual." It is: **automate the arbitered
parts fully; surface a bounded checkpoint at exactly the un-arbitered ones.**

## 3 · The proposal: a campaign orchestrator with bounded checkpoints

A strategic controller that runs the outer loop autonomously *between*
checkpoints, and stops for a human go/no-go *at* each rescope:

```
   ┌── propose campaign + RED-first decomposition + spend estimate  (controller)
   │        │
   │   ◇ CHECKPOINT ── human go / no-go / edit  (accountability + taste + budget)
   │        │ go
   │   arm drafts → RED-first claims                (wave-arming, exists)
   │        │
   │   burn down the slice                          (burndown loop, exists)
   │        │
   │   analyze outcome: closed / parked / substrate landed / dead-end
   │        │
   └────────┘  re-propose next campaign from the new board
```

Between checkpoints it is fully unattended — the parts with an arbiter (does the
claim prove, does the gate pass) run to completion under the kernel. At each
checkpoint it surfaces the parts *without* an arbiter — *which* campaign, *what*
decomposition, *how much* spend — for a human decision that is one of go / no-go /
edit-the-scope. The human supplies accountability and taste; the kernel still
supplies every certification.

## 4 · What it is made of

Mostly composition, with two new pieces:

- **(exists) burndown loop** — works a scoped ledger to done/parked.
- **(exists) wave-arming** — turns drafts into RED-first claims.
- **(exists) fansearch** — proposes discovered candidate claims, gate-confirmed.
- **(exists) `recurve next`** — value-ranks within a ledger.
- **(new) a decomposer** — an agent that turns a named goal (an open node, a
  substrate need) into a set of RED-first *drafts* with probe/trap sketches. This
  is authored, unsound content, so it is treated like any untrusted proposer: the
  gate still confirms each armed claim RED-first, and a *decomposition* is never
  evidence of anything until its claims close.
- **(new) a strategic controller** — reads the board (open / parked / drafts +
  the project's attack plan), proposes the next campaign and hands the
  decomposer a goal, then analyzes each burndown's outcome to re-propose. It is
  the outer loop's driver and the thing that stops at checkpoints.

The novel surface is small: the decomposer, the controller, and the checkpoint
protocol. The load-bearing verification machinery is untouched and reused
verbatim.

## 5 · The checkpoint and spend-budget protocol

The checkpoint is the whole safety story, so it is specified, not incidental:

- **A checkpoint fires at every rescope** — never mid-slice (mid-slice work is
  arbitered, so it needs no human). It presents: the proposed campaign, its
  RED-first decomposition, the rationale (why this, over the ranked
  alternatives), and a **spend estimate** in cycles/tokens.
- **The response is go / no-go / edit** — the operator can approve, decline, or
  rescope, exactly the §7.6 role. Approval is accountability, not judgment: it
  commits *resources*, which the kernel cannot certify and only a human can own.
- **A hard spend budget bounds each autonomous leg.** The orchestrator carries a
  budget (set at the checkpoint); it halts and re-checkpoints when the budget is
  spent, so a misdirected campaign costs at most one budget, not a month. This is
  the direct answer to §2.2.
- **A no-progress guard** — if a decomposition arms claims that all park (a
  gated suite like REG), the orchestrator surfaces that *at the next checkpoint as
  the finding*, rather than looping. Parking is honest information, not a retry
  signal.

Optionally, checkpoints can be batched: an operator can pre-authorize N rescopes
within a total budget for a genuine "set it and sleep" run, trading some
accountability granularity for unattended reach — but the budget ceiling and the
no-progress guard still bind.

## 6 · Provenance

Every controller decision is recorded like a fansearch receipt: which board state
was read, which campaign was chosen over which ranked alternatives and why, what
the decomposer produced, what the checkpoint decided, and the burndown outcome.
A campaign is then reconstructable end to end — the strategy-layer analogue of the
claim-level audit trail, and the thing that lets a human review *taste* after the
fact even though no kernel graded it.

## 7 · Relation to the existing roadmap

This is not a new direction so much as the *composition* of two the framework
already names: §7.1 (a flywheel for workflow and decomposition policies) supplies
the controller's ranking, and §7.4 (automated claim and probe authoring) supplies
the decomposer. The contribution here is the **safety envelope** that lets them
run together autonomously without recreating the self-grading failure — the
checkpoint protocol of §5 — plus the honest accounting that on a fixed budget the
scarce resource is *human accountability for spend*, not generation.

## 8 · Non-goals

- **Not full autonomy.** The un-arbitered decisions (which campaign, what
  decomposition, how much to spend) keep a human checkpoint by design, not by
  present incapacity.
- **Not a new arbiter.** Nothing here grades strategy mechanically; it *surfaces*
  strategy for a human and *bounds* its cost. The kernel remains the sole
  certifier of correctness.
- **Not a shortcut past a gated problem.** An orchestrator pointed at REG still
  parks REG — it just discovers and reports the gate faster. It cannot conjure the
  missing substrate or the missing idea; it can only stop wasting budget on them.

## 9 · Acceptance and phasing

- **Phase 1 (decomposer).** Given a named goal, produce RED-first drafts +
  probe/trap sketches that `baseline` promotes to real open claims; a human
  checkpoint gates the drafts before arming. Reuses wave-arming for the arm step.
- **Phase 2 (controller + checkpoint).** The outer loop: propose → checkpoint →
  arm → burn down → analyze → re-propose, with the spend budget and no-progress
  guard of §5, and the provenance of §6.
- **Phase 3 (batched checkpoints).** Pre-authorized multi-rescope runs under a
  total budget, for unattended operation — the safe form of "burn a whole
  direction while I sleep."
- **Done when:** a session that today is a manual scope↔work ping-pong runs as
  one autonomous leg between two human checkpoints, produces the same
  kernel-verified claims, halts on budget or no-progress rather than drift, and
  leaves a reconstructable record of every strategy decision it made.
