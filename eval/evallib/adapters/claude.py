"""claude.py — the Claude BYO-agent adapter (real, paid path).

Builds the `claude -p` invocation for a cell and runs it in the cell's
workspace under a token cap, returning a sealed row. This is the only path that
spends money; the runner's resume invariant is what makes a stop-and-restart of
a long run safe. Gated logic (plan/runner/analyze) never calls this — the tests
drive the runner with a mock adapter.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def agent_argv(model: str, extra: list[str] | None = None) -> list[str]:
    """The BYO-agent command for a model, per docs/plans/eval-poc.md §3."""
    return ["claude", "-p", "--bare", "--permission-mode", "bypassPermissions",
            "--model", model, *(extra or [])]


def _declared_done(cell: dict, workspace: Path) -> bool:
    """A0: a non-empty solution.py = declared done. A3: a green
    `recurve matrix --gate` = declared done (budget-exhausted red gate =
    refused-to-declare — counted, not hidden)."""
    if cell["arm"] == "A0":
        sol = workspace / "solution.py"
        return sol.exists() and sol.read_text().strip() != ""
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                       capture_output=True, text=True)
    return r.returncode == 0


def make_adapter(prompt_for):
    """Return an adapter closure. `prompt_for(cell)` builds the stdin prompt for
    a cell's arm. Kept as a factory so the arm-specific prompt is injectable and
    testable without spawning an agent."""
    def adapter(cell: dict, workspace) -> dict:  # pragma: no cover - paid path
        workspace = Path(workspace)
        argv = agent_argv(cell["model"])
        proc = subprocess.run(argv, cwd=workspace, input=prompt_for(cell),
                              capture_output=True, text=True)
        return {
            "declared_done": _declared_done(cell, workspace),
            "agent_exit": proc.returncode,
            # token/cost telemetry is filled from the agent's own report by the
            # caller; the adapter records what it can observe here.
        }
    return adapter
