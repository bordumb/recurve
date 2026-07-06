"""core/plan.py — the cross product, generalized to any benchmark's own
task-id key.

`evallib.plan.expand` hardcodes `task["task_id"]` -- exactly right for
BigCodeBench, but SWE-bench's own tasks key on `instance_id` instead
(`evallib.plan.expand` was written before SWE-bench existed in this
codebase; SWE-bench's real pipeline never went through it at all --
`swebench_pipeline.expand_smoke_cells` builds cells directly). Calling
`evallib.plan.expand` on a SWE-bench task list raises `KeyError:
'task_id'` immediately.

This is NOT a case for editing `evallib/plan.py` (out of scope for this
branch) or duplicating its cell-shape/id logic: `cell_id` and
`resolved_gate_config` are already fully generic (a task-id STRING and an
arm NAME respectively -- neither cares what key the caller read it from),
so this only re-does the one line that isn't generic, parameterized by
`task_id_key`. The resulting cell shape is byte-identical to
`evallib.plan.expand`'s own for any benchmark whose `task_id_key ==
"task_id"` (BigCodeBench) -- this isn't a divergent reimplementation, it's
the same loop with the one hardcoded key replaced by a parameter.
"""

from __future__ import annotations

from evallib.plan import cell_id, resolved_gate_config


def expand(manifest: dict, tasks: list[dict], task_id_key: str = "task_id") -> list[dict]:
    """`evallib.plan.expand`, generalized: reads `task[task_id_key]` instead
    of the hardcoded `task["task_id"]`. Every cell still carries its task-id
    coordinate under the literal key `"task_id"` -- the CELL's own
    convention (used uniformly by `core/orchestrate.py`, every benchmark's
    `grade`/`prepare`/`make_routed_agent`) is unrelated to which key the
    TASK dict itself happens to use."""
    m = manifest["matrix"]
    cells = []
    for model in m["models"]:
        for arm in m["arms"]:
            gate_config = resolved_gate_config(arm)
            for budget in m["budgets"]:
                for seed in m["seeds"]:
                    for task in tasks:
                        tid = task[task_id_key]
                        cells.append({
                            "cell_id": cell_id(model, arm, budget, seed, tid),
                            "model": model, "arm": arm, "budget": budget,
                            "seed": seed, "task_id": tid,
                            "instruct_prompt": task.get("instruct_prompt", ""),
                            "gate_config": gate_config,
                        })
    return cells
