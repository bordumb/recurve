"""orchestrate.py — agent → terminal state → held-out oracle → one analyze row.

What a cell *does*, in the order it must happen: run the agent in its
quarantined workspace, confirm the agent process has terminated, read the
final solution.py, grade it against the pinned hidden oracle, and seal a row.
For A3 the row also carries the terminal run-state (gate verdict + why the run
ended) and the outcome class from it, so a refusal is never confused with a
process failure downstream. Every row is self-re-executable (provenance) and
`row_is_complete` refuses one that would leave analyze without its dependent
variable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from evallib.arms import arm_spec
from evallib.classify import classify_gated_run
from evallib.quarantine import OracleTamperError, evaluate

REQUIRED_ROW_FIELDS = (
    "cell_id", "model", "arm", "task_id",
    "declared_done", "oracle_verdict",
    "dataset_revision", "recurve_commit", "adapter_version", "seed",
)


class SequencingError(RuntimeError):
    """Quarantine was attempted before the agent process terminated — the oracle
    may only grade an exited, static workspace, never a live one."""


def row_is_complete(row: dict) -> bool:
    """True iff a row carries everything analyze and reproduction need."""
    return all(k in row for k in REQUIRED_ROW_FIELDS)


def _default_gate(workspace: Path) -> str:
    """The A3 gate verdict from the workspace: green / red / broken."""
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def make_orchestrator(agent, tasks_by_id: dict, pins: dict,
                      provenance: dict, gate_fn=None, oracle_runs: int = 3):
    """Return the adapter the runner drives. `agent(cell, workspace)` runs the
    model and returns at least {terminated: bool}; for A0 it also declares via a
    non-empty solution.py, for A3 it reports its `stop_reason`. `pins` maps
    task_id → the oracle's content-hash recorded at fetch time (each task has
    its own pin), so a tampered oracle is refused per task. The orchestrator
    refuses to quarantine a workspace whose agent has not terminated, then joins
    everything — agent result, terminal state, oracle verdict, outcome class,
    telemetry, provenance — into one row."""
    gate_fn = gate_fn or _default_gate

    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        if not agent_row.get("terminated"):
            raise SequencingError(
                "agent has not terminated — refusing to quarantine a live workspace")

        arm = cell["arm"]
        gate_outcome = None
        terminal_state: dict = {}
        # Branch on the arm's PROPERTY, not its name — a recurve-gated arm may be
        # named anything in the manifest (the full program's arm matrix has more
        # than A0/A3). This mirrors materialize.py's `if spec["recurve"]`.
        if arm_spec(arm)["recurve"]:
            terminal_state = {"gate": gate_fn(workspace),
                              "stop_reason": agent_row.get("stop_reason")}
            gate_outcome = classify_gated_run(workspace, terminal_state)
            declared_done = gate_outcome == "declared"
        else:
            sol = workspace / "solution.py"
            declared_done = sol.exists() and sol.read_text().strip() != ""

        task = tasks_by_id[cell["task_id"]]
        sol = workspace / "solution.py"
        solution_src = sol.read_text() if sol.exists() else ""
        try:
            oracle = evaluate(task, solution_src, pins[cell["task_id"]], runs=oracle_runs)
            verdict, flake = oracle["verdict"], oracle["flake_rate"]
        except OracleTamperError:
            verdict, flake = "tampered", 0.0

        return {
            **{k: cell.get(k) for k in
               ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            "declared_done": declared_done,
            "oracle_verdict": verdict,
            "oracle_flake_rate": flake,
            "gate_outcome": gate_outcome,
            "terminal_state": terminal_state,
            "tokens_in": agent_row.get("tokens_in", 0),
            "tokens_out": agent_row.get("tokens_out", 0),
            "agent_exit": agent_row.get("agent_exit"),
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version")},
        }
    return orchestrate
