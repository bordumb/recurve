# runtime — the autonomous loop's promises, probed

> The agent-runtime spine (`docs/plans/agent-runtime.md` A1-A6). Each claim is the Done condition of a build
> step, guarded by a probe with the step's Wrong condition as a kept counterexample. The actor and adversary
> are pluggable agents; these claims gate the deterministic spine that wraps them.

## Conventions

`missing-surface` claims about `recurvelib.runtime`, `reads: none` — each probe executes the spine against a
stub world / stub actor and a kept counterexample.

## RT-1 — the loop stops by the gate, never the actor's word (A1)

On a one-RED-claim world with a stub actor that emits the fix, `run` reaches STOP-SUCCESS and the world ends
green; with an actor that only *claims* done, `run` never returns STOP-SUCCESS (it reverts on flat progress).
The verdict is a pure function of `world.gate()`. Negative space: a loop that returns STOP-SUCCESS because the
actor signaled done while the gate is still RED must turn the probe RED.

## RT-2 — Sense reports the real uncovered work (A2)

`sense` assembles `uncovered` and the ranked frontier from completeness: a target with one uncovered unit
yields `progress.uncovered == 1` and that unit on the frontier. Negative space: a Sense that reports
`uncovered == 0` on a target with a genuinely uncovered unit must turn the probe RED.

## RT-3 — Sense feeds divergence, so a green-but-diverged cycle does not stop (A3)

`sense` sets `divergent` from fidelity, so an all-probes-green cycle with a passing goal-counterexample
produces `divergent=True` and `decide` does not return STOP-SUCCESS. Negative space: a Sense that drops
divergence (so a diverged-but-green cycle stops with success) must turn the probe RED.

## RT-4 — the write boundary keeps the actor off the referee surface (A4)

`within_boundary` accepts a diff confined to the target tree and rejects any diff touching the referee
surface (claims/probes/traps/gate). Negative space: a boundary that accepts a diff editing a probe must turn
the probe RED.

## RT-5 — the capture rule only accepts a discriminating trap (A5)

`capture` accepts a proposed trap only if it is RED on the wrong implementation AND GREEN on the real one; a
trap that misses the bug, or breaks the real code, is rejected. Negative space: a capture that accepts a trap
which is GREEN on the wrong implementation (catches nothing) must turn the probe RED.

## RT-6 — the actor is reached only on an admitted contract (A6)

`guarded_propose` invokes the actor when the contract is ADMITted and returns None — never calling the actor —
when it is not. Negative space: a guard that invokes the actor on a non-ADMIT contract must turn the probe RED.
