#!/usr/bin/env python3
"""compare_sw6_smoke.py — side-by-side validation: does the refactored grade
port (`src/benchmarks/swebench.py::grade_swe`) reproduce the SAME verdicts
`evallib`'s own pipeline actually produced during the real, paid smoke?

Zero new API spend: this re-runs GRADING ONLY, against the real, still-
on-disk workspaces from `eval/runs/sw6-smoke/workspaces/` (gitignored, not
deleted) — the part that costs real docker/CPU time, never a model call. It
never re-invokes an agent. `evallib` itself is not imported or touched; this
reads its recorded OUTPUT (the committed results file) as the comparison
baseline, and re-derives each cell's diff from the SAME real workspace
`evallib`'s own `extract_diff` already produced it from.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

from src.benchmarks.swebench import grade_swe, prepare_swe  # noqa: E402


def main() -> int:
    real_rows = [json.loads(l) for l in
                (EVAL / "runs" / "sw6-smoke" / "results.jsonl").read_text().splitlines() if l.strip()]
    locks = json.loads((EVAL / "oracle" / "swebench_locks.json").read_text())
    grade = grade_swe(locks)

    print(f"{'cell_id':<58} {'real':>6} {'replay':>7}  match")
    mismatches = []
    skipped = []
    for row in real_rows:
        cell_id = row["cell_id"]
        ws = EVAL / "runs" / "sw6-smoke" / "workspaces" / cell_id
        if not ws.is_dir():
            skipped.append(cell_id)
            print(f"{cell_id:<58} {'(workspace no longer on disk -- skipped)':>14}")
            continue

        task_id = row["task_id"]
        instance = _load_instance(task_id)
        cell = {"task_id": task_id}
        prepare_swe(cell, instance, ws)   # re-extracts the diff into solution.py, same as a real orchestrated cell would
        result = grade(cell, instance, ws)
        replay_verdict = result["verdict"]
        real_verdict = row["oracle_verdict"]
        match = "OK" if replay_verdict == real_verdict else "MISMATCH"
        if match == "MISMATCH":
            mismatches.append(cell_id)
        print(f"{cell_id:<58} {real_verdict:>6} {replay_verdict:>7}  {match}")

    print()
    if skipped:
        print(f"skipped (no on-disk workspace): {len(skipped)}")
    if mismatches:
        print(f"MISMATCHES: {mismatches}")
        return 1
    print("all replayed verdicts match the real, recorded smoke -- OK")
    return 0


def _load_instance(task_id: str) -> dict:
    from evallib.swebench_taskstore import load_pinned
    rows = load_pinned(
        EVAL / "datasets" / "swebench-verified@c104f840cc67f8b6eec6f759ebc8b2693d585d4a.jsonl")
    return next(r for r in rows if r["instance_id"] == task_id)


if __name__ == "__main__":
    raise SystemExit(main())
