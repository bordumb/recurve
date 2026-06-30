# completeness — the coverage layer's promises, probed

> The **frontier** slice of `docs/plans/completeness-layer.md`: a green gate must not mask silent holes.
> Every claim below is guarded by a probe with a kept counterexample — run
> `./recurve --config recurve.toml matrix --gate` and believe the gate, not this prose.

## Conventions

These are enforcement-surface claims about the `recurvelib.frontier` engine module (`missing-surface`),
`reads: none` because each probe *executes* the behavior it guards against a kept counterexample (the trap).

## CL-1 — the frontier is exactly the uncovered surface

A surface point is on the frontier if and only if it is neither covered nor explicitly deferred; the frontier
never admits a covered point and never admits a deferred one. This is what makes "what does no claim cover?"
answerable, and what turns a light user's silent holes into a visible list. Negative space: a frontier that
admits a covered point must turn the probe RED.

## CL-2 — the frontier is ranked highest-risk first

The frontier is ordered by descending weight (ties broken by id, for determinism), so the most valuable
uncovered point is the one claimed next. Negative space: an unranked or ascending frontier must turn the
probe RED.

## CL-3 — coverage accounting is total

Every surface point is classified exactly once: `covered + deferred + uncovered == total`, and the uncovered
count equals the frontier length — no point lost, none double-counted. Totality is what lets the gate say
"this is correct, and here is the precisely-bounded set it says nothing about." Negative space: an accounting
that drops or double-counts a point must turn the probe RED.

## CL-4 — equal-weight frontier points order deterministically by ascending id

Found by an adversarial review of CL-1..3 (a separate agent, per `docs/plans/separation-of-refereeing.md`):
CL-2's fixture used distinct weights, so a tie was never exercised, and an impl that drops the id-tiebreak
ranked equal-weight points nondeterministically — a burndown loop's "next" pick would change run-to-run.
Equal-weight points must come out by ascending id. Negative space: a weight-only sort that lets two
equal-weight points appear in any order other than ascending id must turn the probe RED.

## CL-5 — duplicate ids are classified per-occurrence, never collapsed

CL-3's totality held even for an impl that deduped the surface by id — silently erasing a real, uncovered
surface point from the accounting (the worst kind of coverage hole: the gate reports "nothing uncovered
here" about a point that exists). Two distinct points sharing an id each count toward total. Negative space:
a surface with two same-id points whose reported total is less than the point count must turn the probe RED.

## CL-6 — coverage claimed for an absent id never inflates the accounting

An impl that counted the sizes of the covered/deferred input sets (rather than surface hits) inflated
`covered` with phantom ids and broke the very totality CL-3 defends — yet passed cl-1..3, whose fixtures
carry no phantom ids. `covered`/`deferred` count only surface-present ids. Negative space: a covered id not
on the surface that raises `covered` above the on-surface count, breaking totality, must turn the probe RED.

## CL-7 — public functions and methods both become surface points

Surface extraction (`recurvelib.surface`) emits one point per public unit a claim could cover — a top-level
function AND a public method, each qualified (`func`, `Class.method`) — so the frontier ranks real units of
the target, not just whatever it was handed. Negative space: an adapter that finds only top-level functions
and silently drops class methods must turn the probe RED.

## CL-8 — private code is not surface

Underscore-prefixed functions/methods, and the methods of underscore-prefixed classes, are implementation,
not a claimable surface; extraction excludes them so the frontier never demands a claim for a private. Negative
space: an adapter that surfaces a `_private` name must turn the probe RED.

## CL-9 — surface extraction is deterministic

The same target yields the identical, sorted sequence of points on every run — a surface map is a
*measurement* that must be diffable and stable, or coverage regressions can't be detected. Negative space: an
adapter that returns the right points in a nondeterministic order must turn the probe RED.

## CL-10 — declared coverage aggregates from the claims

The covered set is the union of every claim's `covers` field (a claim that covers nothing contributes
nothing) — the coverage *source* is pluggable behind this seam, with a measured source the stronger upgrade.
Negative space: an aggregator that ignores `covers` and reports nothing covered must turn the probe RED.

## CL-11 — a cycle is complete iff nothing is uncovered

The completeness gate reports `complete` exactly when the frontier is empty — every surface point covered or
deferred. Negative space: a report that calls a cycle complete while points remain uncovered must turn the
probe RED.

## CL-12 — an uncovered point is surfaced, never masked

An uncovered surface point appears on the frontier and flags the cycle incomplete; the gate can never present
a green verdict that silently says nothing about it (the cardinal sin a sound-but-incomplete gate commits).
Negative space: a report that empties the frontier and declares completeness despite an uncovered point must
turn the probe RED.

## CL-13 — an accepted goal-counterexample is divergence

Intent fidelity: a behavior the goal forbids that gets *accepted* makes the cycle divergent, however green the
probes are — soundness and completeness cannot buy back a broken intent. The controller reads divergence to
refuse a success-stop and, if it persists, to revert. Negative space: a divergence check that stays False
while a forbidden behavior is accepted must turn the probe RED.

## CL-14 — no false divergence alarm

When every goal-counterexample is rejected, the cycle is not divergent — intent is intact and progress is
allowed; a spurious alarm would force endless reverts. Negative space: a divergence check that fires while
nothing forbidden was accepted must turn the probe RED.

## CL-15 — divergence names exactly what broke, worst first

`divergent_ids` reports the accepted goal-counterexamples only, ranked by weight, so a revert can name the
most severe breach. Negative space: a report that includes a rejected goal-counterexample, or misorders by
severity, must turn the probe RED.

## CL-16 — an exercised surface point is measured as covered

Measured coverage records the functions a probe actually runs (traced), so a genuinely-exercised point counts
as covered — the strong, non-gameable source behind the `completeness_report` seam. Negative space: a
measurer that runs the exercise but records nothing must turn the probe RED.

## CL-17 — declared is not measured: an unexercised point is not covered

A surface point a probe never executes is not measured as covered, even if a claim declares it — this is the
gap declared coverage cannot close. Negative space: a measurer that reports a point covered without the
exercise running it must turn the probe RED.

## CL-18 — measured coverage carries no phantom points

Calls outside the declared surface (helpers, stdlib) are not phantom coverage; the measured set is restricted
to surface points. Negative space: a measurer that reports an off-surface call as covered must turn the probe
RED.
