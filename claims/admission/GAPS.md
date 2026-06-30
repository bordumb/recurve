# admission — the gateability gate's promises, probed

> Layer 0 (`docs/plans/admission-gate.md`): can a goal become a faithful contract at all? Each claim is
> guarded by a probe with a kept counterexample — run `./recurve --config recurve.toml matrix --gate`. The
> natural-language *judgment* (is an assertion probe-able?) is a rater's input; these claims gate the
> deterministic spine around it (the metric, the worklist, the verdict).

## Conventions

`missing-surface` claims about `recurvelib.admission`, `reads: none` — each probe executes the spine against
rater findings expressed as booleans and a kept counterexample.

## AD-1 — probe-ability is the conjunction of all three criteria

An assertion is probe-able only if it is falsifiable AND has a counterexample AND is bounded; missing any one
disqualifies it. A loose OR would admit a vague assertion on a single virtue. Negative space: a probe-ability
rule that calls an assertion probe-able while it lacks an oracle (or a counterexample, or a bound) must turn
the probe RED.

## AD-2 — gateability is the measured probe-able share

Gateability is `probeable / total` — counted, not rated — and `0.0` for an empty goal. Negative space: a
gateability that reports a fixed or inflated number unrelated to how many assertions are actually probe-able
must turn the probe RED.

## AD-3 — the worklist names exactly the un-probe-able assertions, with their gaps

The diagnostic lists every not-yet-probe-able assertion with its specific named gaps (missing oracle /
counterexample / bound), and never a probe-able one — a worklist, not a score. Negative space: a worklist
that includes a probe-able assertion, or drops the named gaps, must turn the probe RED.

## AD-4 — an all-probe-able goal is admitted

When every assertion is probe-able and the gateable spine is large enough, the verdict is ADMIT — a good
contract is let through. Negative space: a verdict that refuses a goal whose every assertion is probe-able
must turn the probe RED.

## AD-5 — a gateable spine with a vague remainder is refused for interview

When enough assertions are probe-able to form a spine but some remain vague, the verdict is
REFUSE-AND-INTERVIEW (with the worklist) — never ADMIT. Admitting an incomplete contract is the dangerous
failure. Negative space: a verdict that ADMITs a goal while some assertions are not probe-able must turn the
probe RED.

## AD-6 — a too-thin spine is refused as not gateable

When fewer assertions are probe-able than `min_invariants`, the verdict is REFUSE-NOT-GATEABLE — too little
to gate honestly, recommend not gating. Negative space: a verdict that ADMITs or merely interviews a goal
whose probe-able spine is below the minimum must turn the probe RED.
