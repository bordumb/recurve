"""plan.py — manifest → pinned matrix (the cross product, as data).

`expand` turns a manifest and a pinned task set into the full cell list —
task × arm × model × budget × seed — written to matrix.jsonl BEFORE any agent
runs (the registered-report affordance: the sample is committed before results
exist). Cell IDs derive deterministically from coordinates, so a run resumes by
skipping cells whose id is already sealed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_SANITIZE = re.compile(r"[^A-Za-z0-9]+")


def cell_id(model: str, arm: str, budget: int, seed: int, task_id: str) -> str:
    """A stable, filesystem-safe id derived from the cell's coordinates. The
    same coordinates always yield the same id, so re-planning is idempotent and
    a run resumes by id."""
    slug = _SANITIZE.sub("-", f"{model}/{arm}/{budget}/{seed}/{task_id}").strip("-")
    digest = hashlib.sha256(slug.encode()).hexdigest()[:8]
    return f"{slug}-{digest}"


def expand(manifest: dict, tasks: list[dict]) -> list[dict]:
    """The cross product, deterministically ordered. Every cell carries its full
    coordinates plus the task statement (never the hidden test)."""
    m = manifest["matrix"]
    cells = []
    for model in m["models"]:
        for arm in m["arms"]:
            for budget in m["budgets"]:
                for seed in m["seeds"]:
                    for task in tasks:
                        tid = task["task_id"]
                        cells.append({
                            "cell_id": cell_id(model, arm, budget, seed, tid),
                            "model": model, "arm": arm, "budget": budget,
                            "seed": seed, "task_id": tid,
                            "instruct_prompt": task.get("instruct_prompt", ""),
                        })
    return cells


def write_matrix(cells: list[dict], path: str | Path) -> None:
    """Serialize the matrix as JSONL, sorted keys — a diffable, pinned artifact."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "\n".join(json.dumps(c, sort_keys=True) for c in cells) + "\n")
