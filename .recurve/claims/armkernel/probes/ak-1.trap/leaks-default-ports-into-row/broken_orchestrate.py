"""A deliberately-wrong orchestrator: it drops the "only non-default ports
appear in the row" discipline, unconditionally stamping boundary/audit
fields onto EVERY row — the exact regression AK-1's byte-identical fixture
exists to catch. Everything else is copied from the real
evallib.orchestrate so the bug is isolated to that one behavior.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from evallib.arms import arm_spec, resolve_boundary_adapter
from evallib.audit import resolve_audit_port, none_audit
from evallib.done_signal import resolve_done_signal_port
from evallib.quarantine import OracleTamperError, evaluate


class SequencingError(RuntimeError):
    pass


def _default_gate(workspace: Path) -> str:
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def make_orchestrator(agent, tasks_by_id, pins, provenance, gate_fn=None,
                      oracle_runs=3, oracle_timeout=30):
    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        if not agent_row.get("terminated"):
            raise SequencingError("agent has not terminated")

        spec = arm_spec(cell["arm"])
        resolve_boundary_adapter(spec.boundary)
        # BUG: always attach boundary, even at the "enforced" default —
        # every existing arm's row now carries a new key it never had.
        boundary_fields = {"boundary": spec.boundary}

        done_port = resolve_done_signal_port(spec.done_signal)
        done_result = done_port(workspace, agent_row, gate_fn=gate_fn or _default_gate,
                                command=spec.external_ci_command)
        declared_done = done_result["declared_done"]
        gate_outcome = done_result["gate_outcome"]
        terminal_state = done_result["terminal_state"]

        # BUG: always run (and attach) the audit port, even for "none".
        audit_port = resolve_audit_port(spec.audit) if spec.audit != "none" else none_audit
        audit_result = audit_port(workspace)

        task = tasks_by_id[cell["task_id"]]
        sol = workspace / "solution.py"
        solution_src = sol.read_text() if sol.exists() else ""
        try:
            oracle = evaluate(task, solution_src, pins[cell["task_id"]],
                              runs=oracle_runs, timeout=oracle_timeout)
            verdict, flake = oracle["verdict"], oracle["flake_rate"]
        except OracleTamperError:
            verdict, flake = "tampered", 0.0

        row = {
            **{k: cell.get(k) for k in ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            "declared_done": declared_done,
            "oracle_verdict": verdict,
            "oracle_flake_rate": flake,
            "gate_outcome": gate_outcome,
            "terminal_state": terminal_state,
            "tokens_in": agent_row.get("tokens_in", 0),
            "tokens_out": agent_row.get("tokens_out", 0),
            "cost_usd": agent_row.get("cost_usd", 0.0),
            "agent_exit": agent_row.get("agent_exit"),
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version", "oracle_env_hash")},
            **boundary_fields,
            "audit": asdict(audit_result),
        }
        return row
    return orchestrate
