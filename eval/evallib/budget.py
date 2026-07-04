"""budget.py — the token cap, enforced.

Budget-matching is the experiment's key control: A0 and A3 get the same token
cap. But `claude -p` has no hard token cap and `recurve run --cap` bounds
*cycles*, not tokens — so the A3 burndown needs a token-accounting stop.
`TokenBudget` accumulates per-cycle spend and reports exhaustion; `run_capped`
models a burndown that starts a new cycle only while the budget allows,
stopping at (or within one cycle of) the cap, with a hard cycle bound so a
zero-token cycle can never loop forever.
"""

from __future__ import annotations


class TokenBudget:
    """A running token account against a fixed cap."""

    def __init__(self, cap: int):
        self.cap = cap
        self.spent = 0

    def add(self, tokens: int) -> None:
        self.spent += int(tokens)

    def remaining(self) -> int:
        return max(0, self.cap - self.spent)

    def exhausted(self) -> bool:
        return self.spent >= self.cap

    def may_start_cycle(self) -> bool:
        """A new cycle starts only while the budget is not yet exhausted — the
        stop condition for the A3 burndown."""
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
