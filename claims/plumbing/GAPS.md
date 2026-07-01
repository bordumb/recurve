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

## PL-4 — recurve sense assembles the full measured vector ✓

`recurve sense` assembles the measured progress vector — `open`/`regressed`/`broken`
from the gate, `uncovered` from the frontier, `divergent` from fidelity — exactly as
`runtime.sense` does, so the loop can feed the *whole* vector to the controller, not
just the gate counts. The verb's logic (`recurvelib.sense_cli.sense_vector`) mirrors
`runtime.sense`. Negative space (kept RED): a sense that drops the completeness
(`uncovered`) or fidelity (`divergent`) signal — reporting 0 / False — turns the
probe RED.

## PL-5 — the loop feeds the full vector to the controller

`burndown.sh`'s stop decision sources the full vector (via `recurve sense`) and
passes `--uncovered` and `--divergent` to `recurve decide`, so an uncovered frontier
or a divergence blocks `STOP-SUCCESS` — completeness and fidelity, not just the gate,
gate the loop's success. Negative space (kept RED): a loop that calls `decide` with
only `--open/--regressed/--broken` (dropping uncovered + divergent) turns the probe RED.

## PL-6 — the loop admits the goal before it sculpts

The loop runs the admission gate before the first cycle: a `REFUSE-AND-INTERVIEW` /
`REFUSE-NOT-GATEABLE` goal never enters a sculpting cycle — it halts for the human
instead of burning a vague aim into a brittle proxy. Negative space (kept RED): a
loop that sculpts a non-`ADMIT` goal turns the probe RED.
