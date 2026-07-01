---
name: loop
description: Run the improvement loop for probe from inside this session
---

# In-session loop (BROKEN counterexample)

This is the naive version the probe must reject: it keeps the lock and the gate
but works every cycle **in this same session's context**, one after another —
silently losing the clean-agent-per-cycle hygiene. It never spawns a per-cycle
worker of its own.

## Preconditions

```bash
recurve validate
recurve matrix --gate
recurve lock status
recurve lock acquire
```

## The loop

Repeat until done:

1. `recurve next` to pick the highest-value gap.
2. Sculpt the smallest honest change yourself, right here, carrying everything
   you have already learned this session forward into the next cycle.
3. `recurve matrix --gate` to check the gate.

## When you halt

```bash
recurve lock release
recurve matrix
```
