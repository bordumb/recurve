"""telemetry.py — uniform token/cost capture with a dated price table.

The price of trust (tokens, dollars, wall-clock) is a headline metric, so costs
are computed from one dated table, never guessed. Prices are USD per million
tokens, recorded with the date they were read so an old run stays legible after
prices change.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass


def parse_usage(report: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from an agent's JSON usage report
    (e.g. `claude -p --output-format json`). Missing counts read as 0, never
    guessed — an unmeasured run records zero spend, visibly."""
    u = report.get("usage", report)
    return int(u.get("input_tokens", 0) or 0), int(u.get("output_tokens", 0) or 0)


@dataclass
class _Elapsed:
    elapsed: float = 0.0


@contextmanager
def wall_clock():
    """Time a block. `with wall_clock() as t: ...` leaves `t.elapsed` in seconds
    — the wall-clock half of the price of trust."""
    t = _Elapsed()
    start = time.monotonic()
    try:
        yield t
    finally:
        t.elapsed = time.monotonic() - start


# USD per 1M tokens, read 2026-07-04. A model absent here is a hard error at
# cost time, never a silent zero.
PRICES_2026_07_04: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
    "claude-sonnet-5": {"in": 3.0, "out": 15.0},
}
PRICE_TABLE_DATE = "2026-07-04"


def cost_usd(model: str, tokens_in: int, tokens_out: int,
             prices: dict | None = None) -> float:
    """Dollar cost for one cell's token spend. Raises KeyError on an unpriced
    model — an unknown model must not silently cost $0."""
    table = prices or PRICES_2026_07_04
    if model not in table:
        raise KeyError(f"no price for model {model!r} in the {PRICE_TABLE_DATE} table")
    p = table[model]
    return (tokens_in / 1_000_000) * p["in"] + (tokens_out / 1_000_000) * p["out"]


def estimate_usd(cells: list[dict], tokens_per_cell: int | None = None) -> float:
    """A pre-run cost ceiling: every cell at its full budget, split 50/50
    in/out. Deliberately an over-estimate — the number printed before spending."""
    total = 0.0
    for c in cells:
        budget = tokens_per_cell if tokens_per_cell is not None else c.get("budget", 0)
        total += cost_usd(c["model"], budget // 2, budget // 2)
    return total
