"""claude.py — the Claude BYO-agent adapter (real, paid path).

Builds the `claude -p` invocation for a cell and runs it under a per-cell DOLLAR
budget enforced in three layers that do not trust the agent to police its own
spend (a single `claude -p` session spends 143k–1.15M tokens — no token cap can
bound it, per the O6 smoke):

  1. `--max-budget-usd` — the agent's own self-limit for the invocation;
  2. a harness HARD-KILL watchdog (`run_agent_capped`) — SIGKILLs the whole
     process group on a wall-clock overrun, so a runaway session cannot bill on;
  3. for a gated arm, a between-cycle dollar check (`run_gated_burndown`) that
     stops the burndown once the cell's real spend reaches its dollar budget.

Spend is measured from the agent's own `total_cost_usd` (cache-aware), not a
token estimate. Gated logic (plan/runner/analyze) never calls this — the tests
drive the runner with a mock adapter.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# The wall-clock backstop per invocation (seconds). The dollar caps are the fine
# control; this only stops an invocation that hangs or ignores its budget.
WALL_TIMEOUT = 600.0


def agent_argv(model: str, extra: list[str] | None = None) -> list[str]:
    """The BYO-agent command for a model, per docs/plans/eval-poc.md §3.

    No `--bare`: in this environment `--bare` strips whatever injects the session
    auth, so a bare `claude -p` reports "Not logged in". `claude -p
    --permission-mode bypassPermissions` is the working invocation."""
    return ["claude", "-p", "--permission-mode", "bypassPermissions",
            "--model", model, *(extra or [])]


def _run_agent(model, prompt, workspace, budget_usd) -> dict:  # pragma: no cover - paid path
    """One agent invocation under all three spend bounds. Returns
    {returncode, killed, cost_usd, tokens_in, tokens_out}."""
    from evallib.watchdog import run_agent_capped
    from evallib.adapters.telemetry import parse_usage, parse_cost
    argv = agent_argv(model, ["--output-format", "json",
                              "--max-budget-usd", f"{max(0.0, budget_usd):.4f}"])
    r = run_agent_capped(argv, prompt, wall_timeout=WALL_TIMEOUT, cwd=str(workspace))
    ti = to = 0
    cost = 0.0
    try:
        d = json.loads(r["stdout"])
        ti, to = parse_usage(d)
        cost = parse_cost(d)
    except Exception:
        pass
    return {"returncode": r["returncode"], "killed": r["killed"],
            "cost_usd": cost, "tokens_in": ti, "tokens_out": to}


def make_adapter(prompt_for):
    """A single-shot adapter for a bare (non-gated) arm: run the agent once under
    the cell's dollar budget + watchdog, capture real cost and tokens, report
    termination. `prompt_for(cell)` builds the stdin prompt."""
    def adapter(cell: dict, workspace) -> dict:  # pragma: no cover - paid path
        workspace = Path(workspace)
        budget_usd = float(cell.get("budget", 0) or 0)
        a = _run_agent(cell["model"], prompt_for(cell), workspace, budget_usd)
        return {"terminated": True, "agent_exit": a["returncode"],
                "stop_reason": "killed" if a["killed"] else "single_shot",
                "tokens_in": a["tokens_in"], "tokens_out": a["tokens_out"],
                "cost_usd": a["cost_usd"]}
    return adapter


def make_gated_adapter(cycle_prompt_for, cap: float):
    """A gated-arm adapter: drive a recurve burndown under the PER-CELL DOLLAR
    budget (run_gated_burndown), so many fresh per-cycle agents share one budget.
    The budget is read from the cell's own `budget` (dollars; the construction
    `cap` is the fallback). Each cycle runs the agent under `--max-budget-usd` =
    the REMAINING budget plus the hard-kill watchdog, and the gate is re-checked
    between cycles; the loop stops on a green gate or dollar-budget exhaustion, and
    the returned stop_reason is exactly what EV-6 records and EV-7 classifies from."""
    from evallib.budget import run_gated_burndown  # noqa: F401 - paid path

    def adapter(cell: dict, workspace) -> dict:  # pragma: no cover - paid path
        workspace = Path(workspace)
        cell_cap = float(cell.get("budget", cap) or cap)
        spend = {"in": 0, "out": 0, "usd": 0.0}

        def cycle() -> float:
            remaining = max(0.0, cell_cap - spend["usd"])
            a = _run_agent(cell["model"], cycle_prompt_for(cell), workspace, remaining)
            spend["in"] += a["tokens_in"]
            spend["out"] += a["tokens_out"]
            spend["usd"] += a["cost_usd"]
            return a["cost_usd"]   # dollars, for the burndown budget

        def gate_check() -> bool:
            # A fresh recurve workspace has a GREEN gate (no claims to fail), so
            # green alone would declare the cell done before the agent ever ran.
            # "Done" therefore also requires the agent to have expressed the task
            # as a well-formed claim (a probe with a kept trap) — the burndown runs
            # until the agent authors one AND greens it, or the budget is exhausted.
            from evallib.classify import has_wellformed_claim
            return has_wellformed_claim(workspace) and _default_gate_green(workspace)

        result = run_gated_burndown(cell_cap, cycle, gate_check)
        return {"terminated": True, "stop_reason": result["stop_reason"],
                "cycles": result["cycles"],
                "tokens_in": spend["in"], "tokens_out": spend["out"],
                "cost_usd": spend["usd"]}
    return adapter


def _default_gate_green(workspace: Path) -> bool:  # pragma: no cover - paid path
    return subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace,
                          capture_output=True).returncode == 0
