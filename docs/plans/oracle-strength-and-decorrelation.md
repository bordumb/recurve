# PRD — oracle strength and decorrelation: make a GREEN say what backed it

> Scope: recurve **the engine** (`recurvelib/`), not the eval harness. The
> eval's job (`eval-poc.md`/`eval-optimize.md`) is to measure recurve from
> outside; this PRD changes what recurve itself records and shows, so the
> property it measured shows up for every user, on every claim, whether or
> not they ever run a benchmark.

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

### R1 — Oracle tier: recorded, derived, rendered

**Assertion.** Every claim's GREEN carries a recorded **oracle tier**
reflecting what actually backed it, derived automatically from which
passes actually ran against it:

```
self_probe            — RED-first probe only, no trap yet demonstrated
trap_hardened          — probe has rejected its trap (today's baseline GREEN)
fuzz_measured           — drill --fuzz has run against it, FPR recorded
differential_checked    — drill --diff has run against a Gap.reference
adversary_reviewed      — a second agent pass reviewed/attempted refutation
adversary_cross_model   — the above, with a DIFFERENT declared model identity
                          than whichever authored the claim/probe
kernel_verified         — the oracle bottoms out in a sound proof kernel
```

Tier is visible in `recurve ledger` / `recurve show <claim>` output, not
buried in metadata a user has to know to query.

**Counterexamples (traps).**
- A claim with a `reference:` field present but `drill --diff` never
  actually run against it must not render `differential_checked` — the
  field's mere existence is not evidence (ties directly to the *"field
  present, mechanism never exercised"* pattern that would otherwise let
  tier be gamed).
- A tier of `adversary_cross_model` recorded where the adversary run's
  logged model identity equals the actor's logged model identity must be
  refused/demoted (same-model-adversary fixture) — see R2.
- Tier must never be hand-set by the authoring agent. A ledger entry
  whose tier was written directly rather than derived from recorded pass
  evidence must fail validation — self-reported tier is exactly the
  failure mode this PRD exists to prevent.

**Bounds.** Purely additive metadata; does not change gate semantics
(GREEN still means the probe passed and rejected its trap). Existing
ledgers default every claim to `trap_hardened` (today's actual meaning)
with no migration required.

### R2 — Cross-model adversary: a named, identity-enforced mechanism

**Assertion.** The adversary/capture-rule pattern gets a concrete surface:
a claim or suite config knob (e.g. `[gate] adversary = "off" |
"same_model" | "cross_model"`) that runs a second agent pass — under a
**declared, recorded model identity** — to either (a) author an
independent differential probe/reference for `drill --diff`, or (b)
attempt to refute the existing probe under the capture rule (its
objection counts only once captured as a re-runnable trap, per existing
practice). When `cross_model`, the adversary's recorded model identity
must differ from the actor's.

**Counterexamples (traps).**
- An adversary invocation whose recorded model string matches the actor's
  must be refused when the config demands `cross_model` (the exact bug
  class that let the O6 incident through unchallenged).
- A claim tagged `adversary_reviewed` with no adversary run recorded in
  the run log must fail ledger validation.
- **The regression fixture, wired to the actual incident**: replay the
  O6 shape — same-model actor and prober agreeing on a wrong solution —
  through a `cross_model` adversary pass, and the disagreement must
  surface as BROKEN-with-alarm, not silently pass. This is the PRD's
  proof that the mechanism would have caught what just happened.

**Bounds.** Off by default (cost-aware, opt-in per suite/claim — the
house rule applies directly: fuzzing/adversary review are knobs, not
policy). No claim about *which* other model to use beyond "recorded and
different"; provider/model choice is the caller's.

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

## 4 · Sequencing

R1 (tier vocabulary + rendering) is the prerequisite for everything else
being visible → R2 (cross-model adversary surface) and R3 (authoring-time
nudge) build in parallel once R1's vocabulary exists → R4 (reversal
ledger + stats) last, since a reversal event is only informative once it
can report *which tier* was falsified.

## 5 · Acceptance for the wave

- Gate GREEN across the suite; every new claim's probe demonstrated
  RED-first against its trap.
- The O6-incident regression fixture (R2) passes: replayed same-model
  agreement is caught by a cross-model adversary pass.
- `recurve ledger` / `recurve show` render oracle tier for every claim;
  existing ledgers default cleanly to `trap_hardened` with no migration.
- `recurve stats` reports the R4 reversal rate (0/N on a ledger with no
  reversals; correctly non-zero on a ledger carrying the O6-shaped
  fixture).
- No existing claim's GREEN/RED verdict changes — this wave is additive
  metadata and a new opt-in mechanism, not a semantics change.

## 6 · Relationship to the papers

This wave gives the framework paper's residues (§2.9 decorrelation, §7.2
hardening program) a concrete engine feature to cite — moving from "we
name this as an open residue" to "here is the mechanism and the ledger
field that surfaces it." It also gives the economics paper's
miss-correlation ρ (E5) its natural recording surface: R2's cross-model
adversary runs and R4's reversal log are exactly the data E5's measurement
would consume. And it turns the O6 incident from an anecdote the papers
mention in prose into a fixture the engine's own gate can be shown to
catch, reproducibly, on demand.
