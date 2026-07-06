"""done_signal.py — DoneSignalPort: what decides a cell is over, and how.

Three named values, each a pure function `(workspace, agent_row, **kw) ->
dict` returning at minimum `declared_done` (plus `gate_outcome`/
`terminal_state`, present-but-inert for the ports that don't need them, so
every port returns the SAME shape and the caller never has to special-case
one).

`self_report` is built once and shared: A0 (`workspace="bare"`, no ledger
exists to consult) and A6 (`workspace="recurve_init"`, a real ledger IS
present) both use it, and it behaves IDENTICALLY for both — it reads
solution.py and nothing else, ever. A6 does not get its own "ignore the
gate" logic; it gets the SAME function A0 already needed.

`external_ci` is a CLI contract: any shell command, exit 0 = done. Grading
via "the repo's own tests" becomes a config string, not new Python, whenever
a benchmark supplies one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from evallib.classify import classify_gated_run


def _default_gate(workspace: Path) -> str:
    """The A3-family gate verdict from the workspace: green / red / broken."""
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return {0: "green", 1: "red"}.get(r.returncode, "broken")


def gate_done_signal(workspace: Path, agent_row: dict, *, gate_fn=None, **_) -> dict:
    """DoneSignalPort["gate"] — recurve's own measured verdict decides,
    never the agent's word (A3 and every arm built on it). `classify_gated_run`
    still owns the declared/gate_refused/process_failed precedence; this
    port is the slot that calls it."""
    gate_fn = gate_fn or _default_gate
    terminal_state = {"gate": gate_fn(workspace), "stop_reason": agent_row.get("stop_reason")}
    gate_outcome = classify_gated_run(workspace, terminal_state)
    return {"declared_done": gate_outcome == "declared",
            "gate_outcome": gate_outcome, "terminal_state": terminal_state}


def self_report_done_signal(workspace: Path, agent_row: dict, **_) -> dict:
    """DoneSignalPort["self_report"] — the agent's own word, read from
    solution.py alone. Used by A0 (bare workspace: no gate exists to
    consult) AND A6 (recurve_init workspace: a real gate exists, but this
    port never reads it — even a RED gate has zero effect on the recorded
    outcome under this port)."""
    sol = Path(workspace) / "solution.py"
    declared = sol.exists() and sol.read_text().strip() != ""
    return {"declared_done": declared, "gate_outcome": None, "terminal_state": {}}


def external_ci_done_signal(workspace: Path, agent_row: dict, *,
                            command: str = "", timeout: int = 60, **_) -> dict:
    """DoneSignalPort["external_ci"] — any shell command; exit 0 = done, any
    other exit = not yet. The command is the ENTIRE mechanism: plugging in a
    new benchmark's own grading convention ("the repo's own pytest") is a
    config string, zero new Python."""
    if not command:
        raise ValueError("done_signal='external_ci' requires a non-empty command")
    try:
        r = subprocess.run(command, shell=True, cwd=str(workspace),
                           capture_output=True, text=True, timeout=timeout)
        returncode = r.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    return {"declared_done": returncode == 0, "gate_outcome": None,
            "terminal_state": {"external_ci_returncode": returncode}}


DONE_SIGNAL_PORTS = {
    "gate": gate_done_signal,
    "self_report": self_report_done_signal,
    "external_ci": external_ci_done_signal,
}


def resolve_done_signal_port(name: str):
    if name not in DONE_SIGNAL_PORTS:
        raise KeyError(f"unknown done_signal {name!r}; known: {', '.join(DONE_SIGNAL_PORTS)}")
    return DONE_SIGNAL_PORTS[name]
