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

> RT-7..14 were found by an adversarial review of RT-1..6 (`docs/plans/separation-of-refereeing.md`). Seven
> were contract gaps the real spine already handled (the fixtures only exercised one input each); RT-9 was a
> genuine bug — `within_boundary` used `startswith` with no normalization, so `repo/../secret.py` escaped the
> target tree, now fixed by normalizing and rejecting `..`/absolute paths.

## RT-7 — Sense reads the gate counts straight through

`sense` sets `open`/`regressed`/`broken` from the gate mapping; hardcoding one reads a RED world as green and
produces a false STOP-SUCCESS through the sensing seam. Negative space: a Sense that hardcodes or swaps a gate
field (so `sense({"open":5,...})` reports `open=0`) must turn the probe RED.

## RT-8 — the boundary checks every diff path, not just the first

A diff is within-boundary only if *every* path is; a clean file paired with a probe edit is rejected.
Negative space: a boundary that short-circuits on the first clean path and admits a later referee edit must
turn the probe RED.

## RT-9 — a diff path escaping via `..` or absolute is rejected

Paths are normalized; `repo/../secret.py` and `/etc/passwd` escape the target tree and are refused, while a
normal target path still passes. Negative space: a `startswith`-only boundary that admits `repo/../secret.py`
must turn the probe RED.

## RT-10 — the guard refuses every non-ADMIT verdict

`guarded_propose` keys on the ADMIT verdict itself, so a REFUSE-AND-INTERVIEW contract (which has a
probe-able spine) is still refused. Negative space: a guard keyed on the probe-able count rather than the
verdict, so it reaches the actor on a REFUSE-AND-INTERVIEW contract, must turn the probe RED.

## RT-11 — the last-green floor is only a fully-clean cycle

`run` records `last_green` only when `open == regressed == broken == 0`; a regressed cycle never becomes the
revert target. Negative space: a floor keyed on `open == 0` alone, so a regressed cycle is checkpointed and
reverted to, must turn the probe RED.

## RT-12 — STOP-REVERT restores the last-green snapshot, not the current state

On revert `run` restores the recorded `last_green`, rolling back the damage — not the current (worse) state.
Negative space: a revert that restores `world.checkpoint()` (the current state), leaving the damage in place,
must turn the probe RED.

## RT-13 — an already-green world stops before the actor is invoked

`run` checks the verdict every cycle including the first, so a world green on entry returns STOP-SUCCESS
without ever calling the actor. Negative space: a loop that suppresses first-cycle success and runs the actor
against already-done code must turn the probe RED.

## RT-14 — capture rejects a trap that discriminates nothing

`capture` is strict AND, so a trap that is green-on-wrong and red-on-real (nonsense on both axes) is rejected.
Negative space: an XNOR-style capture that accepts the `(False, False)` trap must turn the probe RED.

## RT-15 — the write boundary matches whole path components

`within_boundary` refuses a referee root or anything under it (matched on path segments, not a bare prefix),
so `claims/…` and an exact file named `claims` are refused while a sibling like `claims_backup/x` is allowed —
whether or not the caller wrote the root with a trailing slash. Negative space: a bare-`startswith` match that
refuses `claims_backup/x` under `["claims"]`, or admits an exact-name `claims` file under `["claims/"]`, must
turn the probe RED.
