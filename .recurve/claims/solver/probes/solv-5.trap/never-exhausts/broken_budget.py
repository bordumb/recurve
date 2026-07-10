"""SOLV-5 counterexample: a Budget that never reports exhausted — an unbounded recursion
spins until the test's own 1000-node safety net kicks in instead of solver.py's budget."""

from dataclasses import dataclass


@dataclass
class Budget:
    max_seconds: float | None = None
    max_moves: int | None = None

    def spend_move(self) -> None:
        pass

    def exhausted(self) -> bool:
        return False  # BUG: never stops the recursion
