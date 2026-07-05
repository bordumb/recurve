"""The plausible bug: a budget check that LOGS an overage instead of halting
— the smoke keeps running cells past its ceiling instead of stopping, the
exact "no pilot-scale spend until the smoke is clean" discipline this
requirement exists to enforce.
"""

from __future__ import annotations


class BudgetCeilingExceeded(RuntimeError):
    pass


def assert_within_budget(rows, ceiling_usd):
    total = sum(float(r.get("cost_usd") or 0.0) for r in rows)
    if total > ceiling_usd:
        print(f"warning: over budget (${total:.2f} > ${ceiling_usd:.2f}), continuing anyway")
    return total
