"""smoke.py — the permanent end-to-end smoke, anchored to the substrate.

The first smoke used hand-authored `from solution import` fixtures, and that is
exactly how the namespace-model bug hid: the mock agreed with the harness instead
of the substrate. So the permanent fixture is a REAL pinned BigCodeBench-Hard task
(its real canonical solution + a committed known-bad mutant), and its fidelity to
the substrate is checked, not assumed: `assert_fixture_faithful` refuses a fixture
whose task id is absent from the pinned dataset, or whose test has drifted from the
dataset's own test for that id. `grade_fixture` runs the exact grading convention
(shared-namespace `task_func`) so the smoke can actually detect a bad solution.
"""

from __future__ import annotations

import json
from pathlib import Path


class SmokeFidelityError(RuntimeError):
    """The smoke fixture no longer represents the substrate — refused, so a
    drifted or fabricated fixture cannot pass for the real benchmark."""


def load_fixture(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def assert_fixture_faithful(fixture: dict, dataset_tasks: list[dict]) -> None:
    """Refuse a fixture that is not the substrate's own task: the task id must be
    present in the pinned dataset, and the fixture's `test` must byte-match the
    dataset's test for that id (no idealized edits)."""
    tid = fixture["task_id"]
    match = [t for t in dataset_tasks if t.get("task_id") == tid]
    if not match:
        raise SmokeFidelityError(
            f"smoke fixture {tid} is not in the pinned dataset — a hand-authored "
            f"task cannot stand in for the substrate")
    if match[0].get("test") != fixture["test"]:
        raise SmokeFidelityError(
            f"smoke fixture {tid}'s test has drifted from the pinned dataset — the "
            f"fixture must be the substrate's own test, byte for byte")


def grade_fixture(fixture: dict, *, oracle_runs: int = 1, timeout: int = 60) -> tuple[str, str]:
    """Grade the fixture's canonical solution and its known-bad mutant through the
    real oracle (shared-namespace concatenation). Returns (canonical_verdict,
    mutant_verdict); a sound smoke has ('pass', 'fail'|'error')."""
    from evallib.quarantine import oracle_verdict
    good = oracle_verdict(fixture["test"], fixture["canonical_program"],
                          runs=oracle_runs, timeout=timeout)["verdict"]
    bad = oracle_verdict(fixture["test"], fixture["known_bad_program"],
                         runs=oracle_runs, timeout=timeout)["verdict"]
    return good, bad
