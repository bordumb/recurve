"""SUFF-7 counterexample: the pre-fix sufficiency_ok — reports ok=True from a fresh GREEN
measurement on an already-ledgered gap, but never rewrites its ledger status, because
run_baseline (drafts-only) has nothing to promote for a row already in gaps.yaml."""

from dataclasses import dataclass, field

from recurvelib.core.baseline import run_baseline
from recurvelib.core.conformance import run_matrix
from recurvelib.core.model import load_ledger
from recurvelib.core.probe import Outcome


@dataclass(frozen=True)
class BrokenResult:
    ok: bool
    detail: str
    baseline_outcomes: tuple = ()
    matrix: object = None


def sufficiency_ok(cut, config, write_scaffold=None, today=None, timeout_s=300):
    write_scaffold(cut, config)
    outcomes, _base_ok = run_baseline(config, cut.suite, today or "2026-01-01", timeout_s=timeout_s)

    ledger = load_ledger(config)
    gap = ledger.by_id(cut.assembly_id)
    if gap is None:
        return BrokenResult(ok=False, detail="not in ledger", baseline_outcomes=tuple(outcomes))

    matrix = run_matrix([gap], config, timeout_s=timeout_s)
    result = next((r for r in matrix.results if r.gap.id == cut.assembly_id), None)
    ok = result is not None and result.outcome is Outcome.GREEN and matrix.gate_ok
    # BUG: no promotion path for an already-ledgered gap — ok=True but gaps.yaml untouched.
    return BrokenResult(ok=ok, detail="green (unpromoted)", baseline_outcomes=tuple(outcomes), matrix=matrix)
