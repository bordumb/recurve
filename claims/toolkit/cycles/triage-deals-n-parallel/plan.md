# Sculpting cycle: triage-deals-n-parallel

> One cycle, finished and proven. The cycle is done when every probe below is
> GREEN and `recurve matrix --gate` is green across ALL suites — not just the
> ones that motivated the change.

## Gaps this cycle closes

| gap | suite | severity | class | probe |
| --- | --- | --- | --- | --- |
| TK-7 | toolkit | feature | missing-surface | `tk-7.sh` |

## Smallest fixes (the SCULPT scope — keep it minimal, type-driven)

- **TK-7** — add lanes() to triage (top gap per suite, value-first) and `next --json --lanes N`

## What gets stronger (the REBUILD payoff)

- **TK-7** unlocks: parallel lanes that can never sculpt the same ledger or prose

## Definition of done (the GATE)

- [ ] Every gap probe above flips RED → GREEN (`recurve probe --gap <id>`).
- [ ] `recurve matrix --gate` green across all suites: zero regressions, zero broken.
- [ ] Each touched suite's harness green.
- [ ] Tree changes satisfy the quality constitution (parse-don't-validate,
      ports/adapters, one source of truth); build/lint/tests clean; no suppressions.
- [ ] `gaps.yaml` statuses promoted open→closed; `GAPS.md` prose updated to
      describe the NEW reality (the gap becomes a feature note).
- [ ] Anything discovered mid-cycle that can't be closed is filed as a NEW gap
      with its own RED probe (the loop never silently drops scope).

## Matrix baseline (captured at cycle start)

```
    gap         outcome   status     Δ        detail
  ○ TK-7        RED      open                 ours=no --lanes surface oracle=N disjoint-lane recommendatio

holding 1 · ready_to_close 0 · regressions 0 · broken 0 · stale 0 · missing 0
GATE OK
```
