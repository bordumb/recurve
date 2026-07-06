"""orchestrate.py — the refactored cell-runner: grading promoted to a port.

The pre-refactor orchestrator (`evallib/orchestrate.py`) hardwires
BigCodeBench's own `quarantine.evaluate` call as the ONE non-port step in an
otherwise all-ports pipeline — the exact
reason SWE-bench forked the entire orchestrator (`evallib/swebench_pipeline.py`)
to swap ~15 lines. This module promotes grading to a seventh port: `grade`.

    agent_result = agent(...)                                    # unchanged
    boundary     = apply BoundaryPort[spec.boundary]              # unchanged
    declared     = DoneSignalPort[spec.done_signal](...)          # unchanged
    audit_result = AuditPort[spec.audit](...) if spec.audit != "none" else None  # unchanged
    graded       = grade(cell, task, workspace)                   # <- the new, seventh port
    row = merge(agent_result, declared, audit_result, graded, provenance)

`grade(cell, task, workspace) -> {"verdict": str, "extra_row": dict}` is the
ENTIRE benchmark-specific surface this orchestrator needs. Every other port
(workspace materialization happens before this is called; done_signal/
boundary/audit/adversary/governor) is reused UNCHANGED from `evallib` — this
module never edits or reimplements those adapters, only imports them.

Built alongside `evallib.orchestrate`, never replacing it in place — see
`eval/src/README.md` for why: this lets the SAME `sw6-smoke.toml` cells run
through both implementations and their rows compare byte-for-byte before
`evallib`'s own SWE-bench fork is ever touched.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from evallib.arms import arm_spec, resolve_boundary_adapter
from evallib.audit import resolve_audit_port
from evallib.done_signal import resolve_done_signal_port

REQUIRED_ROW_FIELDS = (
    "cell_id", "model", "arm", "task_id",
    "declared_done", "oracle_verdict",
    "dataset_revision", "recurve_commit", "adapter_version", "seed",
    "oracle_env_hash",
)


class SequencingError(RuntimeError):
    """Grading was attempted before the agent process terminated — the
    oracle may only grade an exited, static workspace, never a live one."""


def row_is_complete(row: dict) -> bool:
    """True iff a row carries everything analyze and reproduction need."""
    return all(k in row for k in REQUIRED_ROW_FIELDS)


def _default_gate(workspace: Path) -> str:  # pragma: no cover - real subprocess
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def _apply_boundary_port(boundary: str) -> dict:
    """Apply BoundaryPort[boundary] to this cell — byte-for-byte the same
    behavior as `evallib.orchestrate._apply_boundary_port` (not imported
    directly, since that name is private to that module; reusing the public
    `resolve_boundary_adapter` registry call it itself uses)."""
    resolve_boundary_adapter(boundary)  # KeyError on an unknown/unregistered value
    if boundary == "enforced":
        return {}
    print(f"BOUNDARY OPEN for cell: arm boundary={boundary!r} — the write "
          f"boundary is DISABLED for this cell (deliberately dangerous, "
          f"opt-in only).", file=sys.stderr)
    return {"boundary": boundary}


def make_orchestrator(agent, tasks_by_id: dict, provenance: dict, *,
                      grade, gate_fn=None):
    """Return the adapter the runner drives. `agent(cell, workspace)` runs the
    model and returns at least `{terminated: bool}`. `grade(cell, task,
    workspace) -> {"verdict": str, "extra_row": dict}` is the ONE
    benchmark-specific slot — BigCodeBench's wraps `quarantine.evaluate`
    (`benchmarks/bigcodebench.py::grade_bcb`); SWE-bench's wraps
    `swebench_quarantine.grade_fresh` + majority-vote + diff extraction
    (`benchmarks/swebench.py::grade_swe`). `extra_row` carries whatever is
    genuinely benchmark-specific about provenance (e.g. SWE-bench's
    per-instance `oracle_env_hash`, or `diff`/`oracle_agreement`) — merged
    LAST, so it can override the shared provenance-derived fields exactly
    where a benchmark's own semantics genuinely differ: carry the
    difference in `extra_row`, never average the two semantics into the
    shared orchestrator itself.

    For an arm at every port's default (boundary="enforced", audit="none")
    the row is byte-identical to a pipeline that never knew those ports
    existed: `boundary`/`audit` keys are only added when a port resolves to
    something other than its inert default."""

    def orchestrate(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        agent_row = dict(agent(cell, workspace))
        if not agent_row.get("terminated"):
            raise SequencingError(
                "agent has not terminated — refusing to grade a live workspace")

        spec = arm_spec(cell["arm"])

        # A slot, not a branch: resolved by NAME, applies to every cell
        # identically regardless of which arm or benchmark it is.
        boundary_fields = _apply_boundary_port(spec.boundary)

        done_port = resolve_done_signal_port(spec.done_signal)
        done_result = done_port(workspace, agent_row,
                                gate_fn=gate_fn or _default_gate,
                                command=spec.external_ci_command)
        declared_done = done_result["declared_done"]
        gate_outcome = done_result["gate_outcome"]
        terminal_state = done_result["terminal_state"]

        audit_result = None
        if spec.audit != "none":
            audit_result = resolve_audit_port(spec.audit)(workspace)

        task = tasks_by_id[cell["task_id"]]
        graded = grade(cell, task, workspace)
        extra_row = graded.get("extra_row", {})

        row = {
            **{k: cell.get(k) for k in
               ("cell_id", "model", "arm", "budget", "seed", "task_id")},
            "declared_done": declared_done,
            "oracle_verdict": graded["verdict"],
            "gate_outcome": gate_outcome,
            "terminal_state": terminal_state,
            "tokens_in": agent_row.get("tokens_in", 0),
            "tokens_out": agent_row.get("tokens_out", 0),
            "cost_usd": agent_row.get("cost_usd", 0.0),
            "agent_exit": agent_row.get("agent_exit"),
            **{k: provenance.get(k) for k in
               ("dataset_revision", "recurve_commit", "adapter_version", "oracle_env_hash")},
            **boundary_fields,
            **extra_row,   # LAST: a benchmark's own semantics win over shared defaults
        }
        if audit_result is not None:
            row["audit"] = asdict(audit_result)
        return row
    return orchestrate
