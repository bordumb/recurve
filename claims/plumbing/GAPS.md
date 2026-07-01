# plumbing — wiring the verification layer into the loop (#4)

> #4, the overarching goal: the loop that runs must admit the goal, sense the
> frontier and divergence, and stop by `controller.decide` — not by mechanical
> watchdogs. These claims surface the verification layer as callable verbs and
> then wire the loop to them. Burned down BY the loop, on its own repo (see
> `claims/self_recursion` for the plumbing that made that possible).

## Conventions

`missing-surface` claims about the recurve engine, `reads: none` — each probe
executes the behavior against a kept counterexample.

## PL-1 — recurve decide surfaces the stopping controller

`recurve decide` runs the stopping controller (`controller.decide`) on a
progress vector and prints the verdict, so the loop — and a human — can ask
recurve what to do from a *measured* vector instead of the cap watchdog deciding
blind. The verb's logic (`recurvelib.decide_cli.verdict_for`) must mirror
`controller.decide` exactly. Negative space: a decide surface whose verdict
disagrees with `controller.decide` (e.g. always STOP-SUCCESS) must turn the
probe RED.
