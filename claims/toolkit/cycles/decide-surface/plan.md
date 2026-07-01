# Sculpting cycle: decide-surface

> One cycle, finished and proven. The cycle is done when every probe below is
> GREEN and `recurve matrix --gate` is green across ALL suites — not just the
> ones that motivated the change.

## Gaps this cycle closes

| gap | suite | severity | class | probe |
| --- | --- | --- | --- | --- |
| PL-1 | plumbing | feature | missing-surface | `pl-1.sh` |

## Smallest fixes (the SCULPT scope — keep it minimal, type-driven)

- **PL-1** — add `recurvelib/decide_cli.py` with `verdict_for(open, regressed,
  broken, uncovered, divergent)` returning `controller.decide([Progress(...)]).value`;
  add `cmd_decide` in `cli.py` that parses a progress vector from flags and prints
  `verdict_for(...)`, register the `decide` subparser, and list it in the module docstring.

## What gets stronger (the REBUILD payoff)

- **PL-1** unlocks: an orchestrator (and a human) can ask recurve for its stop
  verdict from a *measured* progress vector — the stopping controller is now
  wired to a callable surface instead of a blind cap watchdog.

## Definition of done (the GATE)

- [x] Every gap probe above flips RED → GREEN (`recurve probe --gap <id>`).
- [x] `recurve matrix --gate` green across all suites: zero regressions, zero broken.
- [x] Each touched suite's harness green (plumbing has no behavioral harness).
- [x] Tree changes satisfy the quality constitution (thin faithful mirror, one
      source of truth); build/lint/tests clean; no suppressions.
- [x] `gaps.yaml` statuses promoted open→closed; `GAPS.md` prose updated to
      describe the NEW reality (the gap becomes a feature note).
- [x] Anything discovered mid-cycle that can't be closed is filed as a NEW gap
      with its own RED probe (nothing discovered this cycle).

## Matrix baseline (captured at cycle start)

```
    gap         outcome   status     Δ        detail
  ○ PL-1        RED      open                 ours=no `recurve decide` surface yet oracle=verdict_for mirrors controller.decide

holding 116 · ready_to_close 0 · regressions 0 · broken 0 · stale 0 · skipped 1 · missing 0
GATE OK
```
