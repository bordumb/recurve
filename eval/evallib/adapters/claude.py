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


def make_adapter(prompt_for):
    """A single-shot adapter for a bare (non-gated) arm: run the agent once and
    report termination. `prompt_for(cell)` builds the stdin prompt. Kept as a
    factory so the prompt is injectable and testable without spawning an agent."""
    def adapter(cell: dict, workspace) -> dict:  # pragma: no cover - paid path
        workspace = Path(workspace)
        argv = agent_argv(cell["model"])
        proc = subprocess.run(argv, cwd=workspace, input=prompt_for(cell),
                              capture_output=True, text=True)
        return {"terminated": True, "agent_exit": proc.returncode,
                "stop_reason": "single_shot"}
    return adapter


def make_gated_adapter(cycle_prompt_for, cap: int):
    """A gated-arm adapter: drive a recurve burndown under the PER-CELL token cap
    (run_gated_burndown), so many fresh per-cycle agents share one budget. The
    cap is read from the cell's own `budget` (the construction `cap` is only the
    fallback), so a matrix with several budgets bounds each cell by its own. Each
    cycle runs the agent once and the gate is re-checked between cycles; the
    loop stops on a green gate or budget exhaustion, and the returned
    stop_reason is exactly what EV-6 records and EV-7 classifies from."""
    from evallib.budget import run_gated_burndown  # noqa: F401 - paid path
    from evallib.adapters.telemetry import parse_usage

    def adapter(cell: dict, workspace) -> dict:  # pragma: no cover - paid path
        workspace = Path(workspace)
        cell_cap = int(cell.get("budget", cap))
        spend = {"in": 0, "out": 0}

        def cycle() -> int:
            argv = agent_argv(cell["model"], ["--output-format", "json"])
            proc = subprocess.run(argv, cwd=workspace, input=cycle_prompt_for(cell),
                                  capture_output=True, text=True)
            try:
                import json
                ti, to = parse_usage(json.loads(proc.stdout))
            except Exception:
                ti, to = 0, 0
            spend["in"] += ti
            spend["out"] += to
            return ti + to

        def gate_check() -> bool:
            return _default_gate_green(workspace)

        result = run_gated_burndown(cell_cap, cycle, gate_check)
        return {"terminated": True, "stop_reason": result["stop_reason"],
                "cycles": result["cycles"],
                "tokens_in": spend["in"], "tokens_out": spend["out"]}
    return adapter


def _default_gate_green(workspace: Path) -> bool:  # pragma: no cover - paid path
    return subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                          capture_output=True).returncode == 0
