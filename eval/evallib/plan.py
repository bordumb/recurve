"""plan.py — manifest → pinned matrix (the cross product, as data).

`expand` turns a manifest and a pinned task set into the full cell list —
task × arm × model × budget × seed — written to matrix.jsonl BEFORE any agent
runs (the registered-report affordance: the sample is committed before results
exist). Cell IDs derive deterministically from coordinates, so a run resumes by
skipping cells whose id is already sealed.

An arm naming `adversary=`/`governor=` (A7-A10,
docs/plans/ablation-infra.md AI5) has that config resolved through
recurvelib's OWN adapter registry AT PLAN TIME — an unknown arm, or an
unknown adversary/governor value inside a known arm, fails the plan loud,
before any cell is even written, rather than surfacing as a mystery at run
time. The resolved `[gate]` config rides on every cell verbatim (the same
discipline `oracle_env_hash` already applies to the oracle side of a cell).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from evallib.arms import (
    arm_spec, resolve_adversary_adapter, resolve_governor_adapter, resolve_boundary_adapter,
)
from evallib.audit import resolve_audit_port
from evallib.done_signal import resolve_done_signal_port
from evallib.materialize import resolve_workspace_port

_SANITIZE = re.compile(r"[^A-Za-z0-9]+")


def cell_id(model: str, arm: str, budget: int, seed: int, task_id: str) -> str:
    """A stable, filesystem-safe id derived from the cell's coordinates. The
    same coordinates always yield the same id, so re-planning is idempotent and
    a run resumes by id."""
    slug = _SANITIZE.sub("-", f"{model}/{arm}/{budget}/{seed}/{task_id}").strip("-")
    digest = hashlib.sha256(slug.encode()).hexdigest()[:8]
    return f"{slug}-{digest}"


def resolved_gate_config(arm: str) -> dict:
    """The arm's `[gate]`-shaped config, with `adversary=`/`governor=`/
    `boundary=` validated through recurvelib's registry (AI5) — raises
    `KeyError` on an unknown arm, and whatever `resolve_adversary_adapter`/
    `resolve_governor_adapter`/`resolve_boundary_adapter` raise on an unknown
    adapter name. Never silently accepted; a typo'd config value fails the
    plan, not the run.

    Only NON-DEFAULT axes appear in the returned dict — the same convention
    this already followed for adversary=/governor= before boundary= joined
    them: an arm at every default (boundary="enforced") continues to plan
    an identical (`{}`- or few-key-shaped) `gate_config`, byte-for-byte. The
    eval-only axes (`workspace`/`done_signal`/`audit`) are ALSO validated
    here — even though they're never manifest-supplied, a typo'd port name
    in a new arm entry fails the plan loud, not a mystery deep in a run —
    but they are not `[gate]` config, so they never appear in this dict.
    """
    spec = arm_spec(arm)
    resolve_workspace_port(spec.workspace)
    resolve_done_signal_port(spec.done_signal)
    resolve_audit_port(spec.audit)

    config: dict = {}
    if spec.adversary != "off":
        resolve_adversary_adapter(spec.adversary)
        config["adversary"] = spec.adversary
    if spec.governor != "off":
        resolve_governor_adapter(spec.governor)
        config["governor"] = spec.governor
    if spec.boundary != "enforced":
        resolve_boundary_adapter(spec.boundary)
        config["boundary"] = spec.boundary
    return config


def expand(manifest: dict, tasks: list[dict]) -> list[dict]:
    """The cross product, deterministically ordered. Every cell carries its full
    coordinates plus the task statement (never the hidden test) plus its arm's
    resolved [gate] config (adversary=/governor=, validated through the
    registry — recorded verbatim, not just the arm label)."""
    m = manifest["matrix"]
    cells = []
    for model in m["models"]:
        for arm in m["arms"]:
            gate_config = resolved_gate_config(arm)
            for budget in m["budgets"]:
                for seed in m["seeds"]:
                    for task in tasks:
                        tid = task["task_id"]
                        cells.append({
                            "cell_id": cell_id(model, arm, budget, seed, tid),
                            "model": model, "arm": arm, "budget": budget,
                            "seed": seed, "task_id": tid,
                            "instruct_prompt": task.get("instruct_prompt", ""),
                            "gate_config": gate_config,
                        })
    return cells


def write_matrix(cells: list[dict], path: str | Path) -> None:
    """Serialize the matrix as JSONL, sorted keys — a diffable, pinned artifact."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "\n".join(json.dumps(c, sort_keys=True) for c in cells) + "\n")
