"""Sculpting-cycle scaffolding.

A cycle is one pass through the loop (PREFLIGHT→TRIAGE→SCULPT→REBUILD→GATE→
PROMOTE→SNAPSHOT). `cycle new` writes a cycle plan under cycles/<name>/plan.md
that pins exactly the gaps the cycle promises to close and records the matrix
baseline at cycle start.
"""

from __future__ import annotations

from pathlib import Path

from .model import Gap


def write_cycle_plan(
    cycles_dir: Path,
    name: str,
    gaps: list[Gap],
    baseline: str,
    prog: str = "recurve",
    label: str = "suite",
) -> Path:
    cycle_dir = cycles_dir / name
    cycle_dir.mkdir(parents=True, exist_ok=True)
    plan = cycle_dir / "plan.md"

    gap_rows = "\n".join(
        f"| {g.id} | {g.suite} | {g.severity.value} | {g.gap_class.value} | "
        f"`{g.probe.name if g.probe else '—'}` |"
        for g in gaps
    )
    fixes = "\n".join(f"- **{g.id}** — {g.smallest_fix}" for g in gaps)
    unlocks = "\n".join(
        f"- **{g.id}** unlocks: {g.unlocks or '(state what gets stronger when this closes)'}"
        for g in gaps
    )

    plan.write_text(f"""# Sculpting cycle: {name}

> One cycle, finished and proven. The cycle is done when every probe below is
> GREEN and `{prog} matrix --gate` is green across ALL {label}s — not just the
> ones that motivated the change.

## Gaps this cycle closes

| gap | {label} | severity | class | probe |
| --- | --- | --- | --- | --- |
{gap_rows}

## Smallest fixes (the SCULPT scope — keep it minimal, type-driven)

{fixes}

## What gets stronger (the REBUILD payoff)

{unlocks}

## Definition of done (the GATE)

- [ ] Every gap probe above flips RED → GREEN (`{prog} probe --gap <id>`).
- [ ] `{prog} matrix --gate` green across all {label}s: zero regressions, zero broken.
- [ ] Each touched {label}'s harness green.
- [ ] Tree changes satisfy the quality constitution (parse-don't-validate,
      ports/adapters, one source of truth); build/lint/tests clean; no suppressions.
- [ ] `gaps.yaml` statuses promoted open→closed; `GAPS.md` prose updated to
      describe the NEW reality (the gap becomes a feature note).
- [ ] Anything discovered mid-cycle that can't be closed is filed as a NEW gap
      with its own RED probe (the loop never silently drops scope).

## Matrix baseline (captured at cycle start)

```
{baseline}
```
""")
    return plan
