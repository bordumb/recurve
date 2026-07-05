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

> ST-7..11 were found by an adversarial review of ST-1..6 (a separate agent, per
> `docs/plans/separation-of-refereeing.md`). ST-1's only green fixture zeroes `broken`, `regressed`, and
> `divergent` at once, so the three guards that prevent a false "done" were jointly untested; and no probe
> exercised an oscillating history, an empty frontier, a non-stalled pivot, or a stale current item.

## ST-7 — a cycle that is not truly green never stops with success

A latest cycle with `broken > 0` (unmeasured claims), `regressed > 0` (a fresh regression), or `divergent`
(the wrong thing built) does not return `STOP-SUCCESS`, even when `open == uncovered == 0` — zero open work is
not doneness if the work that exists is unmeasured, regressing, or diverged. Negative space: a controller that
returns `STOP-SUCCESS` for any of those cycles must turn the probe RED.

## ST-8 — oscillating remaining-work reverts

When `open + uncovered` ends a `k`-window no lower than it started — including dip-and-return like `[5,1,5]` —
the controller returns `STOP-REVERT`; net-zero progress is non-progress, not a reason to continue forever.
Negative space: a controller that returns `CONTINUE` on an oscillating window whose last value ≥ its first
must turn the probe RED.

## ST-9 — an empty frontier is a clean no-op, not a crash

With no uncovered points, `pick_next` returns `(CONTINUE, None)` and does not raise — frontier exhaustion is
exactly when a clean signal matters most. Negative space: a `pick_next` that raises on an empty frontier must
turn the probe RED.

## ST-10 — a non-stalled item is not pivoted away

When `stalled` is false, `pick_next` keeps the current item regardless of frontier ranking — pivot is for
stuck items, not a per-cycle re-sort that abandons healthy in-flight work. Negative space: a controller that
returns `PIVOT` for a non-stalled current item with a higher-value one available must turn the probe RED.

## ST-11 — a stale current item is reconciled, not echoed

When `current_id` is no longer on the frontier (covered, or never there), `pick_next` reconciles to the
frontier — `(PIVOT, best)` — rather than echoing the dead id back as `CONTINUE`. Negative space: a controller
that returns `(CONTINUE, current_id)` for a `current_id` absent from the frontier must turn the probe RED.

## ST-12 — the governor supersedes STOP_SUCCESS (R5)

`decide()` gains a `governor_status` parameter (`"off"` default — unchanged
behavior for every existing caller). When the gate/mechanical conditions for
success hold: `"off"`/`"cleared"` -> `STOP_SUCCESS` (as before); `"pending"`
(a configured governor has not yet cleared the cycle) -> the new
`PENDING_GOVERNOR` verdict, never `STOP_SUCCESS`; `"vetoed"` -> `CONTINUE`
(the veto becomes a captured trap on the vetoed claim; the cycle keeps
working). `decide()` never invokes a `Governor` itself — the calling loop
measures the status and passes it in, same separation as every other
Progress field.

Negative space: a fully-green cycle with `governor_status="pending"` that
still returns `STOP_SUCCESS` must turn the probe RED — `governor_cleared`
cannot default to true for a cycle that explicitly reports the governor as
not yet run. An unrecognized `governor_status` value must raise, not
silently resolve to some default behavior.
