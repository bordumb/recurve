"""budget.py — the token cap, enforced.

Budget-matching is the experiment's key control: every arm gets the same token
cap. But `claude -p` has no hard token cap and `recurve run --cap` bounds
*cycles*, not tokens — so a gated burndown needs a token-accounting stop.
`TokenBudget` accumulates per-cycle spend and reports exhaustion; `run_capped`
models a burndown that starts a new cycle only while the budget allows,
stopping at (or within one cycle of) the cap, with a hard cycle bound so a
zero-token cycle can never loop forever.
"""

from __future__ import annotations


class TokenBudget:
    """A running account against a fixed cap. Unit-agnostic and float-safe: the
    cap and increments may be tokens (ints) or DOLLARS (fractional) — the account
    never truncates, so a per-cycle cost of $0.12 actually accumulates instead of
    rounding to zero and leaving the cap forever un-hit."""

    def __init__(self, cap):
        self.cap = cap
        self.spent = 0

    def add(self, amount) -> None:
        self.spent += amount

    def remaining(self) -> int:
        return max(0, self.cap - self.spent)

    def exhausted(self) -> bool:
        return self.spent >= self.cap

    def may_start_cycle(self) -> bool:
        """A new cycle starts only while the budget is not yet exhausted — the
        stop condition for a gated burndown."""
        return not self.exhausted()


def run_capped(cap: int, cycle_cost: int, max_cycles: int = 10_000) -> tuple[int, int]:
    """Model a burndown under a token cap. Runs cycles — each costing
    `cycle_cost` tokens — starting a new one only while the budget allows, and
    never more than `max_cycles` (so a zero-cost cycle terminates). Returns
    (cycles_run, tokens_spent)."""
    b = TokenBudget(cap)
    n = 0
    while b.may_start_cycle() and n < max_cycles:
        b.add(cycle_cost)
        n += 1
    return n, b.spent


def run_gated_burndown(cap: int, cycle, gate_check, max_cycles: int = 10_000) -> dict:
    """Drive a recurve-gated burndown (any gated arm) under a PER-CELL token cap
    (not per-cycle: the whole cell's many fresh agents share one budget).
    `cycle()` runs one burndown cycle and returns the tokens it spent;
    `gate_check()` is True once the gate is green. Stop conditions, checked
    before each cycle:

      - gate green            -> stop_reason "gate_green"      (declared done)
      - budget exhausted      -> stop_reason "budget_exhausted" (a refusal)
      - max_cycles reached     -> stop_reason "max_cycles"

    The last cycle may push spend past the cap (a cycle is atomic), so the total
    is bounded by cap + one cycle's cost — never many multiples of it. Returns
    {stop_reason, cycles, tokens_spent}, the terminal state EV-6 records and EV-7
    classifies from."""
    b = TokenBudget(cap)
    n = 0
    while True:
        if gate_check():
            return {"stop_reason": "gate_green", "cycles": n, "tokens_spent": b.spent}
        if b.exhausted():
            return {"stop_reason": "budget_exhausted", "cycles": n, "tokens_spent": b.spent}
        if n >= max_cycles:
            return {"stop_reason": "max_cycles", "cycles": n, "tokens_spent": b.spent}
        b.add(cycle())
        n += 1
