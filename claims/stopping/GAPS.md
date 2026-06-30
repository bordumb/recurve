# stopping — the controller's promises, probed

> The stop / revert / pivot decision (`docs/plans/stopping-controller.md`), decided by *measurement*, not by
> the actor. Every claim is guarded by a probe with a kept counterexample — run
> `./recurve --config recurve.toml matrix --gate` and believe the gate.

## Conventions

`missing-surface` claims about `recurvelib.controller.decide`, `reads: none` — each probe executes the
decision logic against a measured progress history and a kept counterexample.

## ST-1 — a fully-green cycle stops with success

When the latest cycle has no open, regressed, broken, or uncovered work and is not divergent, the controller
returns `STOP-SUCCESS` — the agent does not keep working past done. This is the half an LLM gets wrong by
declaring victory it can't measure or by never wrapping up. Negative space: a controller that returns
`CONTINUE` on a fully-green cycle (the "never stops" failure) must turn the probe RED.

## ST-2 — flat progress reverts, never thrashes forever

When `open + uncovered` work does not shrink over `k` cycles, the controller returns `STOP-REVERT` — bounded
non-progress, never an infinite loop. Negative space: a controller that returns `CONTINUE` after `k` flat
cycles (thrashes forever) must turn the probe RED.

## ST-3 — a converging approach is not abandoned

While open work is still shrinking cycle over cycle, the controller returns `CONTINUE` — it does not give up
on progress (abandoning a plateau about to break is the opposite failure). Negative space: a controller that
returns `STOP-REVERT` while work is decreasing must turn the probe RED.

## ST-4 — work starts on the highest-value frontier point

With no item in progress, the controller picks the highest-value uncovered point (the frontier is ranked
highest-first) — effort goes to what matters most. Negative space: a controller that starts on a lower-value
point when a higher one is available must turn the probe RED.

## ST-5 — a stalled item pivots to a better one

When the current item has stalled and a higher-value item is available, the controller returns `PIVOT` to it
— re-allocating effort rather than grinding a stuck item. Negative space: a controller that returns
`CONTINUE` on a stalled item with a higher-value alternative must turn the probe RED.

## ST-6 — the best item is not pivoted away pointlessly

A stalled item that is already the best is not pivoted off (that is a `decide()` REVERT call, not a pivot);
the controller returns `CONTINUE`. Negative space: a controller that returns `PIVOT` when already on the best
item (a pivot to itself — churn dressed as re-allocation) must turn the probe RED.
