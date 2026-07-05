"""orchestrate.py — agent -> terminal state -> held-out oracle -> one analyze row.

The cell-runner: a FIXED pipeline with slots, each slot filled by a port
lookup keyed on the arm's `ArmSpec` — it never branches on which arm is
running.

    agent_result = agent(...)                                    # unchanged
    boundary     = apply BoundaryPort[spec.boundary]              # loud when open
    declared     = DoneSignalPort[spec.done_signal](...)
    audit_result = AuditPort[spec.audit](...) if spec.audit != "none" else None
    oracle_verdict = quarantine(workspace)                        # unchanged
    row = merge(agent_result, declared, audit_result, oracle_verdict, provenance)

Adding a new arm is a new `ArmSpec` tuple (`evallib.arms`); adding a new PORT
VALUE is one adapter function plus one registry line. Neither ever touches
this function. For an arm at every port's default (boundary="enforced",
audit="none") the row is byte-identical to the pre-port-lookup orchestrator:
the `boundary`/`audit` row fields are only added when a port resolves to
something other than its inert default.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from evallib.arms import arm_spec, resolve_boundary_adapter
from evallib.audit import resolve_audit_port
from evallib.done_signal import resolve_done_signal_port
from evallib.quarantine import OracleTamperError, evaluate

REQUIRED_ROW_FIELDS = (
    "cell_id", "model", "arm", "task_id",
    "declared_done", "oracle_verdict",
    "dataset_revision", "recurve_commit", "adapter_version", "seed",
    "oracle_env_hash",   # WHICH oracle graded this — provenance on par with the dataset revision
)


class SequencingError(RuntimeError):
    """Quarantine was attempted before the agent process terminated — the oracle
    may only grade an exited, static workspace, never a live one."""


def row_is_complete(row: dict) -> bool:
    """True iff a row carries everything analyze and reproduction need."""
    return all(k in row for k in REQUIRED_ROW_FIELDS)


def _default_gate(workspace: Path) -> str:
    """The A3-family gate verdict from the workspace: green / red / broken.
    Kept here (in addition to `evallib.done_signal`'s own copy) purely as the
    historical default `make_orchestrator(..., gate_fn=None)` resolves to —
    identical behavior, not a second implementation of the CHECK itself
    (`classify_gated_run` is the single source of truth for the outcome)."""
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def _apply_boundary_port(boundary: str) -> dict:
    """Apply BoundaryPort[boundary] to this cell.

    Resolves it through recurvelib's OWN registry — never reimplemented —
    so an unknown value fails loud here, before any row is sealed. The
    default ("enforced") adds NOTHING to the row: every arm that stays at
    the default is byte-identical to before this port existed. When it
    resolves to the dangerous "open" capability, that fact is recorded
    LOUDLY: a line to stderr at the moment it is used, plus an explicit,
    unmissable field in the row's own provenance — never silently.
    """
    resolve_boundary_adapter(boundary)  # KeyError on an unknown/unregistered value
    if boundary == "enforced":
        return {}
    print(f"BOUNDARY OPEN for cell: arm boundary={boundary!r} — the write "
          f"boundary is DISABLED for this cell (deliberately dangerous, "
          f"opt-in only).", file=sys.stderr)
    return {"boundary": boundary}


def make_orchestrator(agent, tasks_by_id: dict, pins: dict,
                      provenance: dict, gate_fn=None, oracle_runs: int = 3,
                      oracle_timeout: int = 30):
    """Return the adapter the runner drives. `agent(cell, workspace)` runs the
    model and returns at least {terminated: bool}; for a gated arm it also
    reports its `stop_reason`. `pins` maps task_id -> the oracle's content-hash
    recorded at fetch time (each task has its own pin), so a tampered oracle
    is refused per task. The orchestrator refuses to quarantine a workspace
    whose agent has not terminated, then runs the pipeline (module
    docstring) and joins everything into one row."""

    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        if not agent_row.get("terminated"):
            raise SequencingError(
                "agent has not terminated — refusing to quarantine a live workspace")

        spec = arm_spec(cell["arm"])

        # A slot, not a branch: resolved by NAME, applies to every cell
        # identically regardless of which arm it is.
        boundary_fields = _apply_boundary_port(spec.boundary)

        # The SAME slot serves "gate", "self_report", and "external_ci"; the
        # orchestrator never asks which arm this is, only which done_signal
        # it names.
        done_port = resolve_done_signal_port(spec.done_signal)
        done_result = done_port(workspace, agent_row,
                                gate_fn=gate_fn or _default_gate,
                                command=spec.external_ci_command)
        declared_done = done_result["declared_done"]
        gate_outcome = done_result["gate_outcome"]
        terminal_state = done_result["terminal_state"]

        # Additive only; "none" means the slot is skipped entirely, so an
        # arm that never asked for hardening pays nothing.
        audit_result = None
        if spec.audit != "none":
            audit_result = resolve_audit_port(spec.audit)(workspace)

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
            **{k: cell.get(k) for k in
               ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            "declared_done": declared_done,
            "oracle_verdict": verdict,
            "oracle_flake_rate": flake,
            "gate_outcome": gate_outcome,
            "terminal_state": terminal_state,
            "tokens_in": agent_row.get("tokens_in", 0),
            "tokens_out": agent_row.get("tokens_out", 0),
            "cost_usd": agent_row.get("cost_usd", 0.0),   # the real billed price of this cell
            "agent_exit": agent_row.get("agent_exit"),
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version", "oracle_env_hash")},
            **boundary_fields,
        }
        if audit_result is not None:
            # Namespaced under its own key — structurally cannot collide with
            # declared_done/oracle_verdict regardless of what AuditResult
            # carries: a nested dict can never overwrite a sibling key.
            row["audit"] = asdict(audit_result)
        return row
    return orchestrate
