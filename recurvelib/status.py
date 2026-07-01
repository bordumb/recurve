"""A one-glance health summary of a project's claims.

`summarize` is a pure function: given a parsed ledger and a matrix result, it
returns the counts and the true gate verdict as a plain dict. It computes
`gate_ok` faithfully from the matrix (the same `gate_ok` the `--gate` path
uses) — it never restates a claim's status as if it were the gate's verdict, so
a failed gate can never be reported as passing.
"""

from __future__ import annotations

from typing import Any

from .model import Ledger, Status


def summarize(ledger: Ledger, matrix_result: Any) -> dict:
    """Fold a ledger and a matrix result into a compact health dict.

    Keys:
      open        — count of open/sculpting gaps (the RED backlog)
      closed      — count of closed gaps (GREEN, guarding regression)
      permanent   — count of permanent gaps (facts, never probed)
      gate_ok     — the true gate verdict, taken from the matrix result
      regressions — closed gaps whose probe went RED
      broken      — probes that could not decide
      stale       — probes skipped because their artifacts predate the tree
      skipped     — probes whose external oracle was absent (declared oracle_waiver)
      failed_traps— closed probes that blessed their own counterexample
    """
    open_count = sum(
        1 for g in ledger.gaps
        if g.status in (Status.OPEN, Status.SCULPTING)
    )
    closed_count = sum(1 for g in ledger.gaps if g.status is Status.CLOSED)
    permanent_count = sum(1 for g in ledger.gaps if g.status is Status.PERMANENT)

    return {
        "open": open_count,
        "closed": closed_count,
        "permanent": permanent_count,
        # The verdict is the matrix's own — never recomputed from statuses,
        # never hardcoded. A summary that greenwashed a failed gate would be
        # worse than no summary at all.
        "gate_ok": bool(matrix_result.gate_ok),
        "regressions": len(matrix_result.regressions),
        "broken": len(matrix_result.broken),
        "stale": len(matrix_result.stale),
        "skipped": len(matrix_result.skipped),
        "failed_traps": len(matrix_result.failed_traps),
    }
