"""run_pipeline.py — the per-cell run pipeline, wired end to end.

What a real cell does, in order: materialize a fresh, quarantined workspace,
run the arm-appropriate agent (a single-shot solve for a bare arm; a recurve
burndown under the token cap for a gated arm), grade the result against the
held-out oracle, and hand the runner an analyze-complete row. Both agents are
injectable, so the whole wiring is gated with mocks — no live agent, no spend —
and the bare/gated choice keys on the arm's `recurve` PROPERTY, never its name.
"""

from __future__ import annotations

from pathlib import Path

from evallib.arms import arm_spec
from evallib.materialize import materialize
from evallib.orchestrate import make_orchestrator

# First-draft prompts (the plan expects one refinement after the pilot). The
# bare arm solves; the gated arm must express the task as a falsifiable claim
# and burn it down — and still leave the solution in solution.py, which the
# hidden oracle grades in both arms.
BARE_PROMPT = (
    "Read TASK.md. Implement the requested function(s) in solution.py so the "
    "task is solved. You may write and run your own informal tests. When "
    "solution.py holds your best solution, exit.")

GATED_PROMPT = (
    "Read TASK.md. This workspace is recurve-initialized. Express the task as a "
    "recurve claim: author a RED-first probe (your own test, derived only from "
    "the task statement) and at least one trap (a deliberately-wrong "
    "implementation your probe must reject). Implement the task in solution.py. "
    "Then burn the claim down until `recurve matrix --gate` is green. If you "
    "cannot make the gate green within your budget, stop and do NOT declare "
    "done — a red gate at budget is the honest outcome.")


def _bare_prompt(cell: dict) -> str:
    return BARE_PROMPT


def _gated_prompt(cell: dict) -> str:
    return GATED_PROMPT


def make_pipeline_adapter(tasks_by_id: dict, pins: dict, provenance: dict, *,
                          budget: int, recurve_cmd: str, bare_agent=None,
                          gated_agent=None, gate_fn=None, oracle_runs: int = 3,
                          oracle_timeout: int = 30):
    """Return the adapter `runner.run` drives. Each cell: materialize → the
    arm-appropriate agent → quarantine → sealed row. `bare_agent(cell, ws)` and
    `gated_agent(cell, ws)` are injectable (mocks in the gate, the real Claude
    adapters in a paid run); the choice between them keys on the arm's `recurve`
    property, so a manifest may name a gated arm anything. Constructing the real
    adapters is lazy — a fully-mocked run never imports the live agent."""
    if bare_agent is None or gated_agent is None:
        from evallib.adapters.claude import make_adapter, make_gated_adapter
        bare_agent = bare_agent or make_adapter(_bare_prompt)
        gated_agent = gated_agent or make_gated_adapter(_gated_prompt, budget)

    def routed_agent(cell: dict, workspace) -> dict:
        # A fresh, oracle-quarantined workspace BEFORE the agent ever runs.
        materialize(tasks_by_id[cell["task_id"]], cell["arm"], Path(workspace),
                    recurve_cmd=recurve_cmd)
        agent = gated_agent if arm_spec(cell["arm"])["recurve"] else bare_agent
        return agent(cell, workspace)

    return make_orchestrator(routed_agent, tasks_by_id, pins, provenance,
                             gate_fn=gate_fn, oracle_runs=oracle_runs,
                             oracle_timeout=oracle_timeout)
