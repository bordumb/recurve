"""classify.py — the A3 run outcome: declared / gate_refused / process_failed.

The one distinction that keeps the weak model's numbers honest. A run that
authored a well-formed claim (a probe with a kept trap) and burned it down to a
green gate = *declared*. Same authored state but a red gate at budget = a
genuine *gate refusal* — the gate declining to bless unproven work. A run that
never produced a well-formed claim/probe/trap = a *process failure* (the harness
was never operated), which must NOT be credited to the gate. Reported
separately, per plan §4/§8.3.
"""

from __future__ import annotations

from pathlib import Path


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


def classify_a3(workspace: str | Path, gate_green: bool) -> str:
    """Classify an A3 run. Process failure dominates the label: a run that never
    authored a well-formed claim is `process_failed` regardless of the gate
    verdict (a green gate over no real claim is not a solve). Otherwise a green
    gate is `declared` and a red gate is a genuine `gate_refused`."""
    if not has_wellformed_claim(workspace):
        return "process_failed"
    return "declared" if gate_green else "gate_refused"
