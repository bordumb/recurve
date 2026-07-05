"""A deliberately-wrong external_ci: it "helpfully" also requires a
non-empty solution.py regardless of what the configured command actually
checks — silently smuggling a second, undeclared authority into a port that
is supposed to be a PURE CLI contract (the command is the sole authority;
exit 0 means done, full stop). This is exactly the kind of bug that would
make "grading via an external command requires zero new Python" false: a
benchmark whose own CI command already decides everything would still get a
second, hidden opinion baked into the port.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def external_ci_done_signal(workspace: Path, agent_row: dict, *,
                            command: str = "", timeout: int = 60, **_) -> dict:
    if not command:
        raise ValueError("done_signal='external_ci' requires a non-empty command")
    try:
        r = subprocess.run(command, shell=True, cwd=str(workspace),
                           capture_output=True, text=True, timeout=timeout)
        returncode = r.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    # BUG: a second, undeclared authority — the command is no longer the
    # sole decision-maker.
    sol = Path(workspace) / "solution.py"
    also_has_solution = sol.exists() and sol.read_text().strip() != ""
    return {"declared_done": (returncode == 0) and also_has_solution, "gate_outcome": None,
            "terminal_state": {"external_ci_returncode": returncode}}
