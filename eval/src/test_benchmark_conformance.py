#!/usr/bin/env python3
"""test_benchmark_conformance.py — the thing that keeps the abstraction
honest: one structural check every registered Benchmark must pass, so
adding benchmark #4 without wiring it correctly fails loudly here instead
of silently working "by accident" until someone hits the gap in production.

Scope, honestly stated: this checks STRUCTURE (every registered Benchmark
has a callable `load_tasks`/`grade` producing the right shapes, and
`task_id_key` actually names a key present on its own loaded tasks) for
EVERY registered benchmark, cheaply and hermetically. It does NOT re-run a
full real grading pass (pass/known-wrong/tampered-oracle) for every
benchmark here — that needs real docker and differs per benchmark (a
solution.py for BigCodeBench, a diff for SWE-bench), and is already done
where it matters: `compare_sw6_smoke.py` proves SWE-bench's real grading
semantics against real, recorded results. A deeper, fully benchmark-generic
semantic conformance test (real pass/fail/tamper, per benchmark) is a
reasonable next step, not built here yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import src.benchmarks.bigcodebench  # noqa: F401,E402 -- registers on import
import src.benchmarks.humaneval_plus  # noqa: F401,E402
import src.benchmarks.swebench  # noqa: F401,E402
from src.core.benchmark import known_names, resolve  # noqa: E402


# Each registered benchmark's OWN real, already-committed experiment
# manifest -- a meaningful conformance check reads real config, not an
# empty placeholder every real benchmark would trivially fail on.
_REAL_MANIFEST = {
    "bigcodebench-hard": EVAL / "experiments" / "poc-bcb-hard.toml",
    "swebench-verified": EVAL / "experiments" / "sw6-smoke.toml",
}


def _load_manifest(path: Path) -> dict:
    import tomllib
    return tomllib.loads(path.read_text())


def check_one(name: str) -> list[str]:
    """Returns a list of problems (empty = conformant)."""
    problems = []
    b = resolve(name)

    if not callable(b.load_tasks):
        problems.append("load_tasks is not callable")
    if not callable(b.grade):
        problems.append("grade is not callable (must be a factory)")
    if b.task_id_key not in ("task_id", "instance_id"):
        problems.append(f"unrecognized task_id_key {b.task_id_key!r}")

    manifest_path = _REAL_MANIFEST.get(name)
    manifest = _load_manifest(manifest_path) if manifest_path else {"tasks": {}}

    # load_tasks must produce real dicts carrying task_id_key -- the
    # orchestrator indexes tasks_by_id on exactly this key.
    try:
        tasks = b.load_tasks(manifest, EVAL / "datasets")
    except Exception as e:  # noqa: BLE001 -- report, don't crash the whole sweep
        problems.append(f"load_tasks(real manifest) raised: {type(e).__name__}: {e}")
        tasks = []
    if not tasks:
        problems.append("load_tasks returned zero tasks")
    for t in tasks[:1]:
        if b.task_id_key not in t:
            problems.append(f"a loaded task is missing its own task_id_key ({b.task_id_key!r}): {sorted(t)}")

    return problems


def main() -> int:
    names = known_names()
    if not names:
        print("NO BENCHMARKS REGISTERED -- nothing to check")
        return 1
    failed = False
    for name in names:
        problems = check_one(name)
        if problems:
            failed = True
            print(f"{name}: FAIL")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"{name}: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
