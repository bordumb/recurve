"""The full SWE-bench pipeline, not one port at a time.

Every other test proves ONE port in isolation. This drives all 12 real
sw6-smoke cells through `make_orchestrator` itself (agent -> boundary ->
prepare -> done_signal -> audit -> grade) into `analyze.py`. Driving it for real
is what caught a genuine sequencing bug: `grade_swe` used to write
`workspace/solution.py` AFTER `done_signal` ran, but `done_signal="self_report"`
reads that file immediately -- so a fresh drive-through measured `declared_done`
against a file that did not exist yet. Fixed by splitting the write into
`Benchmark.prepare`, called BEFORE `done_signal`. This test guards against it
recurring.

`oracle_verdict` is pinned (a frozen docker image digest grades it) and is a
hard match for every cell. `declared_done`/`gate_outcome` are hard-checked only
for `done_signal="self_report"` cells (a pure function of a static on-disk
file). For `done_signal="gate"` cells, `recurve matrix --gate` is a live check
against the current engine + workspace state, not a pinned artifact, so its
historical verdict is not guaranteed reproducible once the engine moves on --
that drift is reported, not failed on.

Real inputs: the agent is a stub reusing the already-completed workspaces and
recorded telemetry (zero new spend); docker is real (the oracle's majority-vote
grading). The test skips when the datasets, a docker daemon, or the real on-disk
workspaces are not present in this checkout.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.benchmarks.swebench import (
    default_gate_fn, grade_swe, prepare_swe, resolve_oracle_env,
)
from src.core.orchestrate import make_orchestrator
from src.core.run_manager import resolve_continue_target
from src.core.runner import run as runner_run
from src.analyze import analyze_rows

EVAL = Path(__file__).resolve().parents[1]


def _run_dir() -> Path:
    return resolve_continue_target(EVAL / "experiments", "sw6-smoke", "latest")


def _load_instances() -> dict:
    from evallib.swebench_taskstore import load_pinned
    rows = load_pinned(
        EVAL / "datasets" / "swebench-verified@c104f840cc67f8b6eec6f759ebc8b2693d585d4a.jsonl")
    return {r["instance_id"]: r for r in rows}


def _make_stub_agent(real_rows_by_cell_id: dict):
    """The one thing this test does not drive for real: the coding agent. It
    reuses the real workspace already on disk and the recorded telemetry -- zero
    new spend, zero new agent behavior to account for."""
    def agent(cell: dict, workspace) -> dict:
        recorded = real_rows_by_cell_id[cell["cell_id"]]
        return {
            "terminated": True,
            "tokens_in": recorded["tokens_in"],
            "tokens_out": recorded["tokens_out"],
            "cost_usd": recorded["cost_usd"],
            "agent_exit": recorded["agent_exit"],
        }
    return agent


def test_sw6_end_to_end_replay(require_datasets, require_docker):
    run_dir = _run_dir()
    real_workspaces = run_dir / "workspaces"
    if not real_workspaces.is_dir():
        pytest.skip("real sw6-smoke workspaces are gitignored and not present in this checkout")

    real_rows = [json.loads(l) for l in
                 (run_dir / "results.jsonl").read_text().splitlines() if l.strip()]
    real_by_id = {r["cell_id"]: r for r in real_rows}
    tasks_by_id = _load_instances()
    manifest = tomllib_load(run_dir.parent.parent / "experiment.toml")
    locks = resolve_oracle_env(manifest, repo=EVAL.parent)

    cells = [{"cell_id": r["cell_id"], "model": r["model"], "arm": r["arm"],
              "budget": r["budget"], "seed": r["seed"], "task_id": r["task_id"]}
             for r in real_rows]
    provenance = {"dataset_revision": manifest["tasks"]["revision"],
                  "recurve_commit": "replay", "adapter_version": "replay"}

    orchestrate = make_orchestrator(
        _make_stub_agent(real_by_id), tasks_by_id, provenance,
        grade=grade_swe(locks), gate_fn=default_gate_fn, prepare=prepare_swe)

    with tempfile.TemporaryDirectory() as d:
        results_path = Path(d) / "results.jsonl"
        # keep_workspaces=True -- these are the real evidence directories; this
        # test must never archive-and-delete them.
        runner_run(cells, results_path, orchestrate, real_workspaces,
                   workers=1, keep_workspaces=True)
        new_rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]

    hard_mismatches = []
    for new_row in new_rows:
        real_row = real_by_id[new_row["cell_id"]]
        is_gate_cell = real_row.get("gate_outcome") is not None or new_row.get("gate_outcome") is not None
        for field in ("declared_done", "oracle_verdict", "gate_outcome"):
            # oracle_verdict is pinned (reproducible); self_report declared/gate
            # is a pure function of a static file (reproducible). gate cells'
            # gate_outcome is a live check -- drift there is expected, not failed on.
            hard_check = field == "oracle_verdict" or not is_gate_cell
            if hard_check and real_row.get(field) != new_row.get(field):
                hard_mismatches.append((new_row["cell_id"], field,
                                        real_row.get(field), new_row.get(field)))

    # analyze must run clean over the replayed rows
    analyze_rows(new_rows)
    assert not hard_mismatches, f"pinned fields drifted on replay: {hard_mismatches}"


def tomllib_load(path: Path) -> dict:
    import tomllib
    return tomllib.loads(path.read_text())
