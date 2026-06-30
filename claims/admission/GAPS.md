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

> AD-7..10 were found by an adversarial review of AD-1..6 (`docs/plans/separation-of-refereeing.md`). The
> six fixtures only ever pin spine ∈ {1, 3} at the default `min_invariants`, so the empty goal, the
> single-perfect-assertion case, the `spine == min_invariants` boundary, and the worklist's gap *content*
> were all unexercised. The real spine already handled each; these claims pin them so no reordered/off-by-one
> variant can pass.

## AD-7 — an empty goal is never gateable

`admit([])` is REFUSE-NOT-GATEABLE with gateability `0.0`: zero assertions is no contract, not a perfect one.
Negative space: a verdict that treats "no assertion failed" as "every assertion passed" and ADMITs an empty
goal must turn the probe RED.

## AD-8 — an all-probe-able goal below the minimum is still refused

A single perfectly probe-able assertion (spine 1 < `min_invariants`) is REFUSE-NOT-GATEABLE — "perfectly
probe-able" does not buy back "too few invariants." Negative space: a verdict that ADMITs a fully-probe-able
goal whose spine is below the minimum must turn the probe RED.

## AD-9 — the minimum is an inclusive floor

A spine of exactly `min_invariants` is gateable: ADMIT if all probe-able, REFUSE-AND-INTERVIEW if a vague
remainder — never REFUSE-NOT-GATEABLE. Negative space: an off-by-one that refuses a goal whose spine *equals*
the minimum must turn the probe RED.

## AD-10 — each worklist gap names the specific failed criterion

A gap's text matches which of falsifiable/has_counterexample/bounded actually failed — a missing oracle is
labeled "no oracle," not "unbounded." Negative space: a worklist with the right gap *count* but wrong gap
*content* (mislabeled or constant) must turn the probe RED.

## AD-11 — the interview admits a fully probe-able round

`interview_step` returns ADMIT once the latest round of assertions is fully probe-able — the goal has become
a contract (G3). Negative space: an interview that returns CONTINUE on a fully probe-able round (never
recognizing done) must turn the probe RED.

## AD-12 — the interview escalates instead of looping forever

When `max_rounds` pass with no reduction in the un-probe-able set, `interview_step` returns ESCALATE — the
human cannot name the checks, so the goal is not gateable; it does not interview forever. Negative space: an
interview that returns CONTINUE after a bounded number of no-progress rounds must turn the probe RED.

## AD-13 — the interview is not abandoned while converging

While the un-probe-able set is still shrinking round over round, `interview_step` returns CONTINUE — a goal
about to become gateable is not given up on. Negative space: an interview that returns ESCALATE while the
un-probe-able set is decreasing must turn the probe RED.

## AD-14 — only an admitted goal proceeds to synthesis

`admitted` is true only for an ADMIT report; a REFUSE-AND-INTERVIEW or REFUSE-NOT-GATEABLE goal never reaches
synthesis (G4) — letting one through would bypass the entire gate. Negative space: an `admitted` that returns
true for a non-ADMIT verdict must turn the probe RED.
