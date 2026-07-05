"""A deliberately-wrong self_report: it gives A6 its own bespoke "peek at
the gate anyway if this looks like a recurve workspace" logic — exactly the
regression AK-2 exists to catch. self_report is supposed to read
solution.py and NOTHING else, ever, regardless of workspace.
"""
from __future__ import annotations

from pathlib import Path


def self_report_done_signal(workspace: Path, agent_row: dict, *, gate_fn=None, **_) -> dict:
    sol = Path(workspace) / "solution.py"
    declared = sol.exists() and sol.read_text().strip() != ""
    # BUG: "just in case" gate consultation for a workspace that looks
    # recurve-initialized — the exact bespoke special case this port exists
    # to make unnecessary.
    looks_recurve = (Path(workspace) / ".recurve").exists() or (Path(workspace) / "recurve.toml").exists()
    if looks_recurve and gate_fn is not None:
        if gate_fn(workspace) == "red":
            declared = False
    return {"declared_done": declared, "gate_outcome": None, "terminal_state": {}}
