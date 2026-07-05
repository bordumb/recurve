"""quarantine.py — the held-out oracle, run in isolation.

After the agent process exits, the hidden unittest suite runs against the final
solution.py in a *separate* process (a dedicated bigcodebench venv in a real
run; a clean subprocess here), never inside the agent's workspace. Flake
control: the suite runs N times and the majority verdict wins, with the flake
rate reported. And the oracle itself is pinned — the test text about to grade a
solution must match the checksum recorded at fetch time, so a tampered oracle
is refused rather than trusted.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from evallib.taskstore import content_hash


class OracleTamperError(RuntimeError):
    """The oracle's test text does not match the pin recorded at fetch time."""


def oracle_python() -> str:
    """The interpreter that grades a solution. A real run points
    RECURVE_ORACLE_PYTHON at a dedicated BigCodeBench venv (the heavy third-party
    deps the hidden tests import live there, isolated from the eval tooling's own
    deps); absent that, it falls back to the current interpreter — which is all a
    hermetic, stdlib-only test needs."""
    return os.environ.get("RECURVE_ORACLE_PYTHON") or sys.executable


def _run_once(test_src: str, solution_src: str, timeout: int) -> str:
    """Run the hidden suite once against the solution in an isolated tmpdir.
    Returns 'pass' | 'fail' | 'error'.

    Grades the SUBSTRATE'S namespace: BigCodeBench concatenates the solution and
    the test into ONE module, so the entry point (`task_func`) is a module global
    the test references directly — never `from solution import`. Grading them as
    separate modules turns every correct real solution into an error (an error
    that reads as an oracle failure and inflates shipped-bad-work), so the
    solution and test are joined into a single `oracle_case` module here, exactly
    as the benchmark intends. Nothing is written to the agent workspace."""
    d = Path(tempfile.mkdtemp())
    (d / "oracle_case.py").write_text(solution_src + "\n\n" + test_src)
    try:
        proc = subprocess.run(
            [oracle_python(), "-m", "unittest", "oracle_case", "-v"],
            cwd=d, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "error"
    if proc.returncode == 0:
        return "pass"
    # unittest exits 1 on failures/errors; distinguish an assertion fail from a
    # setup error (import crash) by scanning the report.
    blob = proc.stdout + proc.stderr
    if "FAILED" in blob or "AssertionError" in blob or "FAIL" in blob:
        return "fail"
    return "error"


def oracle_verdict(test_src: str, solution_src: str, runs: int = 3,
                   timeout: int = 30) -> dict:
    """Run the suite `runs` times; return the majority verdict, the vote tally,
    and the flake rate (share of runs disagreeing with the majority)."""
    votes = [_run_once(test_src, solution_src, timeout) for _ in range(runs)]
    tally = Counter(votes)
    verdict, top = tally.most_common(1)[0]
    flake_rate = (runs - top) / runs
    return {"verdict": verdict, "votes": dict(tally), "flake_rate": flake_rate,
            "runs": runs}


def evaluate(task: dict, solution_src: str, pinned_hash: str,
             runs: int = 3, timeout: int = 30) -> dict:
    """Grade a solution against a task's hidden suite, but only after confirming
    the oracle matches its pin. Raises OracleTamperError on any mismatch — a
    tampered or wrong-revision oracle is refused, never trusted to grade."""
    if content_hash([task]) != pinned_hash:
        raise OracleTamperError(
            "oracle test does not match the pinned dataset — refusing to grade")
    return oracle_verdict(task["test"], solution_src, runs=runs, timeout=timeout)
