#!/usr/bin/env python3
"""run_sw6_smoke.py — drive the real SW6 smoke (eval/experiments/sw6-smoke.toml).

No `eval swebench` CLI verb exists yet (flagged in eval/docs' independent
architecture review, Epic B) -- this is a one-off driver, not part of
evallib's core, until that CLI lands. Reuses everything real, unmodified:
`runner.run` (crash-resilient, resumable), `make_swebench_pipeline_adapter`
(real `claude -p` agents + the EV-23/24 dollar-budget watchdog + SW7's
majority-vote grading).

Set SW6_DRY_RUN=1 to drive the exact same wiring with fake agent/grader
(zero cost, zero docker) -- a plumbing check, not a mock of the mechanism
itself (that's what the gated `sw-6.sh` probe already proves forever).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))

from evallib import __version__ as adapter_version  # noqa: E402
from evallib.cli import _git_head  # noqa: E402
from evallib.runner import run as run_cells  # noqa: E402
from evallib.swebench_pipeline import (  # noqa: E402
    expand_smoke_cells, make_swebench_pipeline_adapter, SWE_MODELS_DEFAULT,
)
from evallib.swebench_taskstore import load_pinned  # noqa: E402

DATASET = EVAL / "datasets" / "swebench-verified@c104f840cc67f8b6eec6f759ebc8b2693d585d4a.jsonl"
DATASET_HASH = "076018aaac46ff5a1fb3b584a2e3bc0506a089a929e8bbd9449dd44764213349"
INSTANCE_IDS = ["pallets__flask-5014", "pylint-dev__pylint-4970", "pylint-dev__pylint-4661"]
LOCKS_PATH = EVAL / "oracle" / "swebench_locks.json"
RUN_DIR = EVAL / "runs" / "sw6-smoke"
BUDGET_PER_CELL = 4.0


def main() -> int:
    dry_run = os.environ.get("SW6_DRY_RUN") == "1"

    rows = load_pinned(DATASET, DATASET_HASH, len(INSTANCE_IDS))
    instances_by_id = {r["instance_id"]: r for r in rows}
    for iid in INSTANCE_IDS:
        assert iid in instances_by_id, f"missing instance {iid} in pinned dataset"

    environment_locks = json.loads(LOCKS_PATH.read_text())
    for iid in INSTANCE_IDS:
        if iid not in environment_locks:
            print(f"refusing to run — no environment lock for {iid}; "
                  f"build it first (swebench_env.build_environment_image)", file=sys.stderr)
            return 2

    provenance = {
        "dataset_revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
        "recurve_commit": _git_head(REPO),
        "adapter_version": adapter_version,
    }

    cells = expand_smoke_cells(INSTANCE_IDS, models=SWE_MODELS_DEFAULT, budget=BUDGET_PER_CELL)
    print(f"{len(cells)} cells total (models={SWE_MODELS_DEFAULT}, arms=A0/A9, "
          f"instances={INSTANCE_IDS})")

    run_dir = RUN_DIR if not dry_run else RUN_DIR.parent / "sw6-smoke-dryrun"

    if dry_run:
        def fake_agent(cell, workspace):
            return {"terminated": True, "agent_exit": 0, "stop_reason": "single_shot",
                     "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.0, "container_id": "fake"}

        def fake_grader(inst, diff_text, digest, agent_container_id=None, **kw):
            return {"resolved": True, "report": {}, "grading_container_id": "fake"}

        def fake_gate_fn(ws):
            return "green"

        adapter = make_swebench_pipeline_adapter(
            instances_by_id, environment_locks, provenance,
            budget=BUDGET_PER_CELL, recurve_cmd="recurve",
            bare_agent=fake_agent, gated_agent=fake_agent,
            gate_fn=fake_gate_fn, grader=fake_grader,
        )
    else:
        adapter = make_swebench_pipeline_adapter(
            instances_by_id, environment_locks, provenance,
            budget=BUDGET_PER_CELL, recurve_cmd="recurve",
        )

    workers = int(os.environ.get("SW6_WORKERS", "1"))
    n = run_cells(cells, run_dir / "results.jsonl", adapter, run_dir / "workspaces", workers=workers)
    print(f"invoked {n} new cell(s) this run (workers={workers}); "
          f"results -> {run_dir / 'results.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
