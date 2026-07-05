"""classify.py — a gated run's outcome: declared / gate_refused / process_failed.

For any recurve-gated arm (A3 in the POC; the full program's arm matrix has
more), the one distinction that keeps the weak model's numbers honest cannot be
read from the workspace alone: whether a red gate is a genuine *refusal* (a
well-formed claim burned down until the token budget ran out) or a *process
failure* (the harness was never operated, the run crashed, or a probe could not
even decide) turns on the **terminal run-state** — why the run ended — which the
orchestrator records from telemetry, not something the workspace holds. So
`classify_gated_run` takes both: the authored workspace state AND the terminal
state.

The classifier attests only what workspace + run-state can attest — `declared`
(gate green) — never "solved"; only the held-out oracle knows if anything was
solved.
"""

from __future__ import annotations

from pathlib import Path

# terminal_state["gate"]: the final gate verdict for the cell.
GATE_GREEN, GATE_RED, GATE_BROKEN = "green", "red", "broken"
# terminal_state["stop_reason"]: why the run ended.
STOP_GATE_GREEN, STOP_BUDGET, STOP_CRASHED = "gate_green", "budget_exhausted", "crashed"


def has_wellformed_claim(workspace: str | Path) -> bool:
    """True iff the workspace contains at least one probe with a kept trap
    fixture — evidence the agent actually expressed the task as a falsifiable
    claim, rather than failing to operate the harness at all."""
    for probe in Path(workspace).rglob("*.sh"):
        if probe.parent.name != "probes":
            continue
        trap = probe.parent / (probe.stem + ".trap")
        if trap.is_dir() and any(p.is_dir() for p in trap.iterdir()):
            return True
    return False


def classify_gated_run(workspace: str | Path, terminal_state: dict) -> str:
    """Classify a recurve-gated run from (authored state, terminal state).

    Precedence, so a process failure is never credited to the gate:
      1. no well-formed claim ever authored          -> process_failed
      2. gate BROKEN (a probe could not decide)       -> process_failed
      3. gate GREEN                                    -> declared
      4. gate RED, ended because the budget ran out    -> gate_refused
      5. gate RED, ended any other way (crash/error)   -> process_failed
    """
    gate = terminal_state.get("gate")
    stop = terminal_state.get("stop_reason")
    if not has_wellformed_claim(workspace):
        return "process_failed"
    if gate == GATE_BROKEN:
        return "process_failed"
    if gate == GATE_GREEN:
        return "declared"
    if gate == GATE_RED and stop == STOP_BUDGET:
        return "gate_refused"
    return "process_failed"
