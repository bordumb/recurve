"""BROKEN counterexample for TK-20: a summarize that reports gate_ok=True even
when the matrix result's own gate failed. This is the one thing the summary
must never do — hand back a passing verdict over a failed gate, so a reader
trusts a health block that hides regressions or broken probes."""


def summarize(ledger, matrix_result):
    open_count = sum(
        1 for g in ledger.gaps
        if g.status.value in ("open", "sculpting")
    )
    closed_count = sum(1 for g in ledger.gaps if g.status.value == "closed")
    return {
        "open": open_count,
        "closed": closed_count,
        "permanent": 0,
        # The defect: the verdict is nailed to True regardless of the matrix.
        "gate_ok": True,
        "regressions": len(matrix_result.regressions),
        "broken": len(matrix_result.broken),
        "stale": len(matrix_result.stale),
        "failed_traps": len(matrix_result.failed_traps),
    }
