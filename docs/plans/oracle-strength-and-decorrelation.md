# PRD — oracle strength and decorrelation: make a GREEN say what backed it

> Scope: recurve **the engine** (`recurvelib/`), not the eval harness. The
> eval's job (`eval-poc.md`/`eval-optimize.md`) is to measure recurve from
> outside; this PRD changes what recurve itself records and shows, so the
> property it measured shows up for every user, on every claim, whether or
> not they ever run a benchmark.
>
> The *how* — ports/adapters, isolation strategy, and the context-sharing
> mechanism for R2's adversary and R5's governor — is specified separately
> in [ablation-infra.md](ablation-infra.md), so this PRD's requirements
> stay in R2/R5's terms (assertion/trap/bounds) rather than architecture.

## 1 · Why now — a real incident, not a hypothetical

During the O6 live smoke (2026-07-05, BigCodeBench/13, arm A3, model
`claude-sonnet-5`): the agent authored its own claim and its own RED-first
probe from the task statement, closed the claim, and the gate went
**GREEN**. A held-out oracle the agent never saw — BigCodeBench's hidden
test suite — says the solution **fails**. Same model, same misreading,
wrote both the work and the check that approved it.

This is not a new failure mode. It is the framework's own named residue —
correlated authorship (framework paper §2.6, §2.9) and its economic
formalization as miss-correlation ρ (companion economics paper §3.3) — but
until now it was *asserted*, not *witnessed*. It just happened, for real,
on the first live cell, before a single row of pilot data existed.

The gap this exposes is specific: **recurve's ledger cannot currently
distinguish a GREEN that a same-model self-authored probe approved from a
GREEN that survived an independent check.** Both render identically. A
user reading `recurve ledger` sees GREEN either way and has no way to know
which claims are load-bearing on a single model's blind spot.

Mechanisms to address this **already exist** in the engine and are not
being reinvented here: `Gap.reference` + `drill --diff` (differential
probes against a stricter reference oracle, `recurvelib/core/model.py`),
`drill --fuzz` (false-positive measurement), `drill --iso` (isomorphic
trap generation), and `oracle_waiver` (a named reason a probe's external
oracle may be absent). What does **not** exist: any recorded notion of
*which* of these actually backed a given GREEN, and any mechanized,
identity-checked notion of a cross-model adversary — "adversary" today is
prose in `runtime.py`, not a CLI surface with an enforced actor/reviewer
identity distinction.

There is a second, distinct gap the incident exposes, worth naming
separately: the deterministic controller (`decide()`) that decides
STOP_SUCCESS trusts the gate's verdicts unconditionally —
`STOP_SUCCESS ⇔ open=regressed=broken=uncovered=0 ∧ ¬divergent`. If every
claim in a cycle is green because of the *same* shared blind spot, the
controller correctly reports success by its own rules, and is still
wrong. R1–R4 harden the check that produces a single claim's GREEN; R5
below adds a superseding check on the *run's decision to report itself
done*, so a compromised gate is not the controller's only source of truth
even in the worst case where every individual claim was, on its own
terms, honestly checked.

## 2 · Non-goals

- Not rebuilding the claim/probe/trap/gate core model.
- Not solving specification-equivalence in general (§2.6) — open by
  construction; this PRD buys back trust probabilistically, the same
  posture as existing traps and fuzz, not a general solve.
- Not touching `eval/` — that harness measures recurve from outside; this
  PRD is about what recurve itself records, independent of any benchmark.
- Not mandating cross-model review on every claim. Per house rule ("make
  it a parameter users can turn on or off"), this is opt-in and
  cost-aware — doubling agent cost on claims it's applied to is a real
  trade, not a free upgrade.
- Not blocking GREEN on a weak oracle tier. The framework's ethic is
  honesty over refusal (§2.8, "beyond soundness") — make the weakness
  *legible*, don't forbid it.

## 3 · Requirements

Each requirement is one or more claims: assertion, counterexample (trap),
bounds — the same shape the PRD is asking recurve's own gate to record.

### R1 — Oracle tier: recorded, derived, rendered — and honest about what backs it

**Assertion.** Every claim's GREEN carries a recorded **oracle tier**
reflecting what actually backed it, derived automatically from which
passes actually ran against it. The tier vocabulary is split along the
axis this PRD's design discussion surfaced: **mechanical checks (no
model in the loop, no correlated-error risk) are a different kind of
evidence than LLM-backed checks (risk-reduced, never risk-free), not
merely a stronger point on the same ladder:**

```
self_probe                — RED-first probe only, no trap yet demonstrated
trap_hardened               — probe has rejected its trap (today's baseline GREEN)
fuzz_measured                — drill --fuzz has run against it, FPR recorded
adversary_reviewed            — a second agent pass reviewed/attempted refutation
adversary_cross_model          — the above, with a VERIFIED-different model
                                identity (see R2) than whichever authored
                                the claim/probe
differential_checked_llm       — drill --diff ran against a Gap.reference
                                that is itself LLM-authored — bounded by
                                the same correlated-error ceiling as the
                                adversary tiers, not above them
differential_checked_mechanical — drill --diff ran against a Gap.reference
                                that is a mechanical ground truth (a real
                                interpreter/library run, a fixed dataset,
                                a golden output) — no model in the check,
                                categorically stronger
kernel_verified                — the oracle bottoms out in a sound proof kernel
```

The dividing line is explicit and load-bearing: **`adversary_cross_model`
and `differential_checked_llm` reduce correlated error; they do not
eliminate it, because two LLMs can share training-era blind spots even
with zero shared context.** `differential_checked_mechanical` and
`kernel_verified` have no such ceiling — there is no judgment call to
correlate. A claim's `reference:` field must record which kind of
reference it points at so the derivation isn't guessing.

Tier is visible in `recurve ledger` / `recurve show <claim>` output, not
buried in metadata a user has to know to query.

**Counterexamples (traps).**
- A claim with a `reference:` field present but `drill --diff` never
  actually run against it must not render either `differential_checked_*`
  tier — the field's mere existence is not evidence (ties directly to the
  *"field present, mechanism never exercised"* pattern that would
  otherwise let tier be gamed).
- A `reference:` pointing at an LLM-authored implementation must not
  render `differential_checked_mechanical` — the mechanical/LLM
  distinction must be verifiable from what the reference actually is
  (e.g., is it executable ground truth with no model invocation in its
  own construction?), not asserted by whoever wrote the claim.
- A tier of `adversary_cross_model` recorded where the adversary run's
  *verified* model identity (§R2) equals the actor's must be
  refused/demoted (same-model-adversary fixture) — see R2.
- Tier must never be hand-set by the authoring agent. A ledger entry
  whose tier was written directly rather than derived from recorded pass
  evidence must fail validation — self-reported tier is exactly the
  failure mode this PRD exists to prevent.

**Bounds.** Purely additive metadata; does not change gate semantics
(GREEN still means the probe passed and rejected its trap). Existing
ledgers default every claim to `trap_hardened` (today's actual meaning)
with no migration required.

### R2 — Cross-model adversary: isolated by construction, verified not declared

**Assertion.** The adversary/capture-rule pattern gets a concrete surface:
a claim or suite config knob (e.g. `[gate] adversary = "off" |
"same_model" | "cross_model"`) that runs a second agent pass to either
(a) author an independent differential probe/reference for `drill
--diff`, or (b) attempt to refute the existing probe under the capture
rule (its objection counts only once captured as a re-runnable trap, per
existing practice). Two properties make this real isolation rather than
a declared one:

- **Context isolation, mechanical, by construction.** The adversary
  invocation runs in a **fresh, isolated executor** — the same shape as
  the oracle's own isolation (`RECURVE_ORACLE_PYTHON`/
  `RECURVE_ORACLE_IMAGE`): a new subprocess, a **read-only** mount of
  only the ledger artifacts under review (claim, probe, solution), a
  scrubbed environment, and *no* access to the acting agent's live
  session, scratch files, or reasoning trace. This is fully guaranteeable
  and cheap — it is process hygiene, not a model property — and it holds
  for `same_model` review too (still worth doing: even the same model
  reviewing without its own prior reasoning in context is a real,
  if weaker, check).
- **Identity verification, not declaration.** "Different model" must be
  checked against the **actual served model**, not the requested one — the
  API response/transcript metadata's own model field, verified post hoc —
  because a self-reported `--model` string can be wrong by config bug
  without anyone lying. When `cross_model` is configured, the run refuses
  if the *verified* served identity for the adversary pass matches the
  *verified* served identity recorded for whichever pass authored the
  claim/probe.

**What this does NOT claim (see R1):** cross-model review reduces
correlated error; it does not eliminate it. Two different models can
share training-era blind spots with zero shared context. This mechanism
is bounded by that ceiling, honestly, in its tier (`adversary_cross_model`,
not `kernel_verified`).

**Counterexamples (traps).**
- An adversary invocation whose *verified* served model matches the
  actor's *verified* served model must be refused when the config
  demands `cross_model` — checked from response metadata, not the
  `--model` flag that was merely requested (the exact bug class that let
  the O6 incident through unchallenged, plus the config-drift case where
  the flag says one thing and the server did another).
- An adversary invocation given filesystem or environment access beyond
  the read-only artifact mount (e.g., it can see the acting agent's
  working directory, shell history, or prior conversation) must be
  refused — isolation-boundary fixture, mirroring the oracle's own
  workspace-must-not-contain-the-oracle trap.
- A claim tagged `adversary_reviewed` with no adversary run recorded in
  the run log must fail ledger validation.
- **The regression fixture, wired to the actual incident**: replay the
  O6 shape — same-model actor and prober agreeing on a wrong solution —
  through a `cross_model` adversary pass, and the disagreement must
  surface as BROKEN-with-alarm, not silently pass. This is the PRD's
  proof that the mechanism would have caught what just happened.

**Bounds.** Off by default (cost-aware, opt-in per suite/claim — the
house rule applies directly: fuzzing/adversary review are knobs, not
policy). No claim about *which* other model to use beyond "recorded,
different, and verified"; provider/model choice is the caller's.

### R3 — Surface the weak-oracle question during authoring, not after

**Assertion.** Claim drafting (`recurve-plan`'s interview, `recurve
admit`) actively asks/nudges: *could an independent reference or
adversary pass be obtained for this claim?* A claim that closes on
`self_probe` or `trap_hardened` alone, with no `reference:`, no adversary
pass, and no `oracle_waiver` reasoning, surfaces an advisory note —
visible in `recurve ledger`, not silent.

**Counterexamples (traps).** A claim whose `reference:` field was added
after the fact purely to suppress the advisory, with `drill --diff` never
actually run, must still show the advisory (ties to R1's anti-gaming
trap — presence of the field is not evidence of the pass having run).

**Bounds.** Advisory only, never blocks GREEN — consistent with §2.8's
stance that recurve makes weak-oracle work legible rather than refusing
to certify it.

### R4 — Reversal events: when a GREEN is later falsified, log it, don't launder it

**Assertion.** If a claim closed GREEN and is subsequently shown wrong by
any stronger check — a later differential pass, a follow-up adversary
catching it, or an external oracle in an evaluation context — that
reversal is recorded as a **distinct ledger event type** (not a silent
park/reopen), carrying the tier the claim held when it was falsified.
Standing run statistics (`recurve stats`) report the reversal rate
alongside existing close%/trap-debt figures, defaulting to 0/N until any
reversal occurs.

**Counterexamples (traps).** A claim silently reopened and reclosed with
no trace of the original false GREEN must be refused — this is the
"measure, don't launder" ethic applied to the engine's own history, not
just its probes. A reversal event missing the tier-at-time-of-falsification
field must fail validation (without it, "what tier of GREEN turned out
to be wrong" — the single most useful question this feature answers — is
unanswerable).

**Bounds.** This is the honesty/measurement backstop, not a prevention
mechanism — R1–R3 are prevention; R4 exists because prevention will
sometimes fail anyway. That is the paper's whole point: trust is graded,
not absolute.

### R5 — The governor: a superseding, run-level check on STOP_SUCCESS itself

**Assertion.** R2 hardens the probe *before* a single claim closes. R5 is
a different check, at a different point: an authority the controller
must clear *in addition to* the gate before it may honor STOP_SUCCESS —
so a run where every individual claim was, on its own terms, honestly
gated can still be stopped, reopened, or forced to restart if the
governor objects. Two tiers, deliberately priced differently:

- **Mechanical tier (near-free, no LLM; default candidate).** Before a
  cycle's STOP_SUCCESS is honored, every probe *and* every trap the
  cycle closed is re-executed in a fresh, isolated checkout — not the
  working directory the burndown loop used — and checked for drift (has
  the claim's proposition text or probe file changed since it was
  gated?). This catches a different bug class than correlated
  authorship: state leakage, "works in this working directory,"
  accidental trap-weakening mid-run. Cost is one re-execution pass over
  work already done; no new agent calls.
- **Review tier (costs tokens; opt-in, recommended default for
  unattended/autonomous runs).** A single decorrelated-model pass reviews
  the *batch* of newly-green claims from the cycle — one review call per
  batch, not per claim, which is why it is affordable where R2's
  per-claim adversary is not — with the power to veto specific claims
  back to RED before the run may report itself done. This is precisely
  the scenario the O6 incident occurred in: an autonomous run, nobody
  watching claim-by-claim. It reuses R2's isolation and verification
  machinery exactly: a fresh, read-only-mounted executor with no access
  to the burndown loop's live session, and a *verified* (not declared)
  served-model identity.

**The `/recurve-work` plumbing gap this exposes, concretely.** Endless
mode currently drives the whole loop with one invocation —
`recurve run --agent 'claude -p --bare --permission-mode
bypassPermissions'` — **with no `--model` at all**, so every cycle,
including any future governor pass, silently inherits whatever the
operator's CLI default happens to be. There is today no lever to give the
governor a distinct invocation from the main loop. This PRD requires a
new, separate **`RECURVE_GOVERNOR_CMD`**, plumbed the same way
`RECURVE_ORACLE_PYTHON`/`RECURVE_ORACLE_IMAGE` are separate from the
main agent command — the governor cannot be "whatever the loop happens
to default to," it must be independently configured or the isolation
guarantees above have no invocation to attach to.

The controller's formal decision rule changes to reflect this:
`STOP_SUCCESS ⇔ (open=regressed=broken=uncovered=0 ∧ ¬divergent) ∧
governor_cleared`. When the mechanical/gate conditions hold but the
governor has not yet run or has objections, the cycle reports a new
state — not STOP_SUCCESS, not plain CONTINUE — call it
`PENDING_GOVERNOR`, which resolves to STOP_SUCCESS on a clean pass or
reopens the vetoed claims with the veto reason as next-cycle context
(mirroring a validation-and-retry loop: a rejection carries its reason
forward, it is not a bare "no"). This is a real change to `decide()`,
gated by its own claim(s) alongside the existing `ST-1..8` stopping
suite — call it `ST-9`.

**The constraint that keeps the governor from becoming a second
unaccountable authority:** a veto must become a **new trap on the vetoed
claim, per the existing capture rule** — never a bare "redo it." The
governor is required to articulate a falsifiable, re-checkable reason the
same way any other adversary objection must be captured before it counts.
Without this, a compromised self-graded gate would simply be replaced by
an opaque governor opinion — a regression in auditability, not a fix.

**Counterexamples (traps).**
- A cycle that reaches STOP_SUCCESS with the governor never having run
  (mechanical tier skipped, or review tier configured on but not invoked)
  must be refused — `governor_cleared` cannot default to true.
- A governor veto recorded with no captured trap on the vetoed claim must
  fail validation — an uncaptured veto is exactly the unaccountable-second-
  authority failure this requirement exists to prevent.
- A review-tier invocation running under `RECURVE_GOVERNOR_CMD` unset
  (silently falling back to the main loop's `AGENT_CMD`/CLI default) must
  be refused, not quietly accepted as "cross-model" — the governor must
  be demonstrably configured, not assumed distinct.
- A review-tier pass whose *verified* served model equals the *verified*
  served model of the cycle's own claim-authoring passes must be refused
  from clearing `governor_cleared` — same identity-verification
  requirement as R2, applied at run level.
- **The regression fixture, wired to the actual incident, at the run
  level this time**: replay the O6 shape as a full cycle — every claim's
  own gate green, all sharing one correlated-authorship defect — through
  the mechanical tier (must NOT catch it; drift/tamper is not the bug
  here, correctly) and then the review tier (must catch it and veto,
  producing a captured trap). This proves the two tiers' distinct
  coverage, not just that "a governor exists."
- Repeated vetoes on the same claim without resolution must not loop
  forever: check first whether the existing `STOP_REVERT` thrashing
  detection (no net reduction in open+uncovered over the last k=3
  cycles) already absorbs this for free — a claim stuck in
  veto/reopen/veto looks identical to any other stalled claim from the
  controller's point of view — before building new bounding machinery.

**Bounds.** A suite/run config knob, same shape as R2's:
`[gate] governor = "off" | "mechanical" | "mechanical_review"`.
`mechanical`: default-on candidate (cost is re-execution of existing
work, no new agent calls). `mechanical_review`: off by default, same
house rule as R2 (a parameter, not a policy), but documented as the
recommended setting for endless/unattended burndown mode specifically —
the mode with no human watching individual closes, which is the mode the
incident happened in. R5 does not replace R4: R5 is preventive (before
the run reports done), R4 is the backstop for whatever R5 still misses
(after).

## 3a · Ablatability: independent switches, recorded configs, a ladder not a factorial

Every mechanism in this PRD must compose freely with the switches that
already exist (`[gate] traps`, `drill --fuzz/--iso/--diff`) and with each
other, so an arm is always just "which switches were on," never a
special case. Three properties make that true:

- **R2 (adversary) and R5 (governor) are orthogonal knobs, not a bundled
  feature.** `[gate] adversary = off|same_model|cross_model` and
  `[gate] governor = off|mechanical|mechanical_review` are independent —
  either can be on with the other off, so a run can isolate "what does
  per-claim adversary review add" from "what does the run-level governor
  add" instead of only ever measuring them together. Colloquially
  "governor/adversary" is one *concept* (decorrelation) but two separate
  *switches*, deliberately, because marginal detection per layer (the
  same metric §7's E1 interception experiment already uses) requires
  turning each on alone before turning both on together.
- **The resolved config is recorded verbatim, not just an arm label.**
  Every claim/run row carries the actual `[gate]` values in effect
  (traps, adversary, governor, plus the existing fuzz/iso/diff knobs) —
  the same discipline the eval's `oracle_env_hash` already applies to the
  oracle environment. An arm name like "A7" is a convenience label; the
  row must be re-derivable from its own recorded config alone.
- **Extend the ladder, don't build a factorial.** `traps × fuzz × iso ×
  diff × adversary(3) × governor(3) × boundary × controller` is already
  8+ dimensions; a full cross product is hundreds of arms — unaffordable
  and mostly uninformative (most cells differ from their neighbor by one
  switch no one asked about). `eval-full.md`'s existing arm matrix is
  already a **ladder** (cumulative: A0 → A2 → A3 → A4) plus a small set
  of **leave-one-out** arms subtracted from the ladder's strongest rung
  (A5 boundary-off, A6 controller-off) — the standard, affordable
  ablation-study shape. This PRD's switches extend the same ladder rather
  than starting a new design:

```
A0  no-recurve                      (existing — the control)
A2  claims + probes, traps off      (existing — "recurve, minimally")
A3  claims + probes + traps         (existing — default discipline)
A4  A3 + fuzz/iso/diff              (existing — hardened probes)
A7  A3 + adversary=cross_model      (new — per-claim decorrelation alone)
A8  A3 + governor=mechanical        (new — free run-level check alone)
A9  A3 + governor=mechanical_review (new — run-level decorrelation alone)
A10 A3 + adversary=cross_model
       + governor=mechanical_review (new — full stack)
A5  A3, boundary off                (existing — leave-one-out)
A6  A3, controller off              (existing — leave-one-out)
```

This maps directly onto the user-facing shorthand: "0% recurve" = A0,
"claims only" = A2, "claims + traps" = A3, "claims + traps +
governor/adversary" = A10 — with A7–A9 as the intermediate rungs that
make the combination's marginal contribution measurable rather than
assumed. `eval-full.md` §4's arm matrix and table gain A7–A10
accordingly; the POC (`eval-poc.md`) keeps its existing {A0, A3} scope
unchanged — these are E4/ablation-phase arms, not POC arms.

## 4 · Sequencing

R1 (tier vocabulary + rendering) is the prerequisite for everything else
being visible → R2 (cross-model adversary surface: isolation executor +
identity verification) and R3 (authoring-time nudge) build in parallel
once R1's vocabulary exists → R4 (reversal ledger + stats) → R5 (the
governor) last, since its mechanical tier depends on nothing new but its
review tier reuses R2's isolation-executor and identity-verification
machinery directly (not a reimplementation — the same code path,
invoked via the new `RECURVE_GOVERNOR_CMD`), and its veto-capture
requirement reuses R4's reversal-event vocabulary (a veto is a reversal
caught before publication rather than after).

## 5 · Acceptance for the wave

- Gate GREEN across the suite; every new claim's probe demonstrated
  RED-first against its trap.
- The O6-incident regression fixture (R2) passes: replayed same-model
  agreement is caught by a cross-model adversary pass.
- The isolation-boundary fixture (R2) passes: an adversary/governor
  invocation cannot see the acting agent's live session, working
  directory, or prior reasoning — only the read-only-mounted artifacts.
- Identity verification is real: a fixture where the requested `--model`
  differs from the actual served model (simulated config drift) is
  caught — tier/`governor_cleared` derive from verified, not requested,
  identity.
- `recurve ledger` / `recurve show` render oracle tier for every claim,
  using the mechanical/LLM-split vocabulary (R1); existing ledgers
  default cleanly to `trap_hardened` with no migration.
- `recurve stats` reports the R4 reversal rate (0/N on a ledger with no
  reversals; correctly non-zero on a ledger carrying the O6-shaped
  fixture).
- The R5 run-level regression fixture passes: the mechanical tier
  correctly does *not* catch the correlated-authorship replay, the
  review tier does, and the veto lands as a captured trap, not a bare
  rejection.
- `decide()` gains `ST-9` (governor-gated STOP_SUCCESS) without breaking
  `ST-1..8`; a cycle cannot reach STOP_SUCCESS with `governor_cleared`
  unset.
- No existing claim's GREEN/RED verdict changes — this wave is additive
  metadata and new opt-in/default-cheap mechanisms, not a semantics
  change to any already-closed claim.

## 6 · Relationship to the papers

This wave gives the framework paper's residues (§2.9 decorrelation, §7.2
hardening program) a concrete engine feature to cite — moving from "we
name this as an open residue" to "here is the mechanism and the ledger
field that surfaces it." It also gives the economics paper's
miss-correlation ρ (E5) its natural recording surface: R2's cross-model
adversary runs, R4's reversal log, and R5's captured vetoes are exactly
the data E5's measurement would consume. And it turns the O6 incident
from an anecdote the papers mention in prose into a fixture the engine's
own gate — at both the single-claim (R2) and whole-run (R5) level — can
be shown to catch, reproducibly, on demand.

R5 also gives `eval-full.md`'s ablation arm matrix a natural new arm
alongside A5 (boundary off) and A6 (controller off): an A7 with the
governor on vs. off, so the governor's marginal detection is measured by
the same harness that motivated building it, rather than asserted.
