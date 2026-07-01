# plumbing — wiring the verification layer into the loop (#4)

> #4, the overarching goal: the loop that runs must admit the goal, sense the
> frontier and divergence, and stop by `controller.decide` — not by mechanical
> watchdogs. These claims surface the verification layer as callable verbs and
> then wire the loop to them. Burned down BY the loop, on its own repo (see
> `claims/self_recursion` for the plumbing that made that possible).

## Conventions

`missing-surface` claims about the recurve engine, `reads: none` — each probe
executes the behavior against a kept counterexample.

## PL-1 — recurve decide surfaces the stopping controller ✓

`recurve decide` runs the stopping controller (`controller.decide`) on a
progress vector read from flags (`--open/--regressed/--broken/--uncovered/--divergent`)
and prints the verdict, so the loop — and a human — can ask recurve what to do
from a *measured* vector instead of the cap watchdog deciding blind. The verb's
logic (`recurvelib.decide_cli.verdict_for`) is a thin faithful mirror of
`controller.decide`: it wraps the vector in a one-cycle history and returns the
verdict's string value, adding no policy of its own, so it can never disagree
with the referee it exposes. Negative space (kept RED as a counterexample): a
decide surface whose verdict disagrees with `controller.decide` (e.g. always
STOP-SUCCESS) turns the probe RED.

## PL-2 — recurve frontier surfaces the completeness frontier ✓

`recurve frontier` reports the ranked uncovered surface for a target, so the loop
— and a human — can see what no claim covers. The verb's logic
(`recurvelib.frontier_cli.frontier_ids`) mirrors `compute_frontier`'s ranked
frontier exactly. Negative space (kept RED as a counterexample): a frontier
surface that hides uncovered points (e.g. always returns an empty list) turns the
probe RED.

## PL-3 — the burndown loop's stop decision consults controller.decide ✓

The burndown loop no longer declares itself "burned down" by the empty-backlog
watchdog alone. When the strict ledger and drafts both empty, `burndown.sh`
measures the cycle's gate vector — `open` (RED/open gaps) from `recurve next
--json`, `regressed` and `broken` parsed from the `recurve matrix` summary line —
and calls `recurve decide` on it. The success-halt fires ONLY when the
controller's verdict is `STOP-SUCCESS`; any other verdict (a regression or an
unmeasurable claim that no open gap tracks) halts for the human instead of
claiming victory. The cap, consecutive-failure, and runaway watchdogs remain as
backstops. This is the #4 wiring: the loop's stop verdict comes from
`controller.decide`, not the ad-hoc cap. Negative space (kept RED as a
counterexample): a loop that calls `decide` but never branches on `STOP-SUCCESS`
— the verdict computed for show while the watchdog still decides — turns the
probe RED.
