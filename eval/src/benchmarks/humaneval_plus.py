"""humaneval_plus.py — a trivial third benchmark, proving the abstraction
actually generalizes: adding it touches only this ONE file, plus the single
`register()` call at its bottom. No orchestrator change, no registry
change beyond that one call.

This is deliberately NOT a real, usable benchmark: `load_tasks` returns a
single hand-written task and `grade` does a bare string-equality check
against a fabricated "canonical" answer stashed in the task dict itself
(never a real hidden-test oracle) — real quarantine, real held-out tests,
and real dataset fetching are all out of scope here on purpose. Its only
job is to exercise the shared orchestrator end to end with a genuinely
different (if toy) grading rule, proving a benchmark that isn't
BigCodeBench or SWE-bench can plug in at all. Delete this file once that's
proven, or keep it if a real HumanEval+ port is ever wanted — either way,
nothing outside this file needs to change either time.
"""

from __future__ import annotations

from pathlib import Path

from src.core.benchmark import Benchmark, register


def grade_humaneval_plus():
    """The grade factory takes no run-specific arguments at all here — the
    toy "canonical answer" lives directly on each task dict, not in a
    separately-pinned oracle file, since this benchmark never claims to be
    a real one."""
    def grade(cell: dict, task: dict, workspace) -> dict:
        sol = Path(workspace) / "solution.py"
        solution_src = sol.read_text() if sol.exists() else ""
        verdict = "pass" if solution_src.strip() == task["canonical_answer"].strip() else "fail"
        return {"verdict": verdict, "extra_row": {}}
    return grade


def _load_tasks(manifest: dict, cache_dir) -> list[dict]:
    return [{
        "task_id": "toy/1",
        "instruct_prompt": "write add(a, b) returning the sum",
        "canonical_answer": "def add(a, b):\n    return a + b\n",
    }]


register(Benchmark(
    name="humaneval-plus-stub",
    load_tasks=_load_tasks,
    task_id_key="task_id",
    grade=grade_humaneval_plus,
))
