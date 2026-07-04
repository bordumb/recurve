"""orchestrate.py — agent → held-out oracle → one analyze-ready row.

The runner drives cells; the orchestrator is what a cell *does*: run the agent
in its quarantined workspace, read the final solution.py, grade it against the
pinned hidden oracle (never in the workspace), and seal a row that carries both
the agent's `declared_done` and the oracle's `oracle_verdict` — plus per-row
provenance so any single row is re-executable from its own fields. A row that
omits the oracle verdict or its provenance is refused: that is the one shape
that would leave `analyze` without its dependent variable.
"""

from __future__ import annotations

from pathlib import Path

from evallib.quarantine import OracleTamperError, evaluate

# Every sealed row must carry these — the coordinates, the two outcomes, and the
# provenance that makes it self-re-executable (§5 rule 2).
REQUIRED_ROW_FIELDS = (
    "cell_id", "model", "arm", "task_id",
    "declared_done", "oracle_verdict",
    "dataset_revision", "recurve_commit", "adapter_version", "seed",
)


def row_is_complete(row: dict) -> bool:
    """True iff a row carries everything analyze and reproduction need. The
    guard that keeps a run-only (declared_done-only) row out of the dataset."""
    return all(k in row for k in REQUIRED_ROW_FIELDS)


def make_orchestrator(agent, tasks_by_id: dict, pinned_hash: str,
                      provenance: dict, oracle_runs: int = 3):
    """Return an adapter the runner can drive. `agent(cell, workspace)` runs the
    model and returns at least {declared_done}; the orchestrator then grades the
    workspace's solution.py with the held-out oracle and merges everything —
    agent result, oracle verdict, coordinates, provenance — into one row.

    The hidden tasks (`tasks_by_id`) and the pin are held out-of-band, never
    materialized into the workspace."""
    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        task = tasks_by_id[cell["task_id"]]
        sol = workspace / "solution.py"
        solution_src = sol.read_text() if sol.exists() else ""
        try:
            oracle = evaluate(task, solution_src, pinned_hash, runs=oracle_runs)
            verdict, flake = oracle["verdict"], oracle["flake_rate"]
        except OracleTamperError:
            verdict, flake = "tampered", 0.0
        row = {
            **{k: cell.get(k) for k in
               ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            **agent_row,
            "oracle_verdict": verdict,
            "oracle_flake_rate": flake,
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version")},
        }
        return row
    return orchestrate
