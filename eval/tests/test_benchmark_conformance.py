"""One structural check every registered Benchmark must pass, so adding
benchmark #4 without wiring it correctly fails loudly here instead of silently
working "by accident" until someone hits the gap in production.

Scope, honestly stated: this checks STRUCTURE (every registered Benchmark has a
callable `load_tasks`/`grade` producing the right shapes, and `task_id_key`
actually names a key present on its own loaded tasks). It does not re-run a full
real grading pass (pass/known-wrong/tampered-oracle) for every benchmark — that
needs real docker and differs per benchmark, and is covered where it matters
(compare_sw6_smoke.py proves SWE-bench's real grading against recorded results).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

# Registration is also done in conftest; importing here keeps the parametrize
# list correct regardless of collection order.
import src.benchmarks.bigcodebench  # noqa: F401
import src.benchmarks.humaneval_plus  # noqa: F401
import src.benchmarks.swebench  # noqa: F401
from src.core.benchmark import known_names, resolve

EVAL = Path(__file__).resolve().parents[1]

# Each registered benchmark's own real, already-committed experiment manifest —
# a meaningful conformance check reads real config, not an empty placeholder.
_REAL_MANIFEST = {
    "bigcodebench-hard": EVAL / "experiments" / "poc-bcb-hard" / "experiment.toml",
    "swebench-verified": EVAL / "experiments" / "sw6-smoke" / "experiment.toml",
}


def check_one(name: str) -> list[str]:
    """Every structural problem with a registered benchmark (empty = conformant)."""
    problems = []
    b = resolve(name)

    if not callable(b.load_tasks):
        problems.append("load_tasks is not callable")
    if not callable(b.grade):
        problems.append("grade is not callable (must be a factory)")
    if b.prepare is not None and not callable(b.prepare):
        problems.append("prepare is neither None nor callable")
    if b.task_id_key not in ("task_id", "instance_id"):
        problems.append(f"unrecognized task_id_key {b.task_id_key!r}")

    manifest_path = _REAL_MANIFEST.get(name)
    manifest = tomllib.loads(manifest_path.read_text()) if manifest_path else {"tasks": {}}

    # load_tasks must produce real dicts carrying task_id_key -- the orchestrator
    # indexes tasks_by_id on exactly this key.
    try:
        tasks = b.load_tasks(manifest, EVAL / "datasets")
    except Exception as e:  # noqa: BLE001 -- collect, don't crash the sweep
        problems.append(f"load_tasks(real manifest) raised: {type(e).__name__}: {e}")
        tasks = []
    if not tasks:
        problems.append("load_tasks returned zero tasks")
    for t in tasks[:1]:
        if b.task_id_key not in t:
            problems.append(f"a loaded task is missing its own task_id_key ({b.task_id_key!r}): {sorted(t)}")

    return problems


def test_benchmarks_are_registered():
    assert known_names(), "no benchmarks registered -- nothing to check"


@pytest.mark.parametrize("name", known_names())
def test_benchmark_is_conformant(name, require_datasets):
    problems = check_one(name)
    assert problems == [], f"{name}: " + "; ".join(problems)
