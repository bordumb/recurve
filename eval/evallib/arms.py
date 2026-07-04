"""arms.py — arm name → workspace spec (pure).

An arm is how a cell is set up before the agent runs. The mapping is a pure
function so the matrix stays data: adding an arm is a table entry, not new code.
The arm names A0/A3 come from the full program's arm matrix (eval-full.md).
"""

from __future__ import annotations

# recurve: whether the workspace is `recurve init`-ed before the agent runs.
# config: extra recurve.toml settings the arm stamps (empty for the POC arms).
_ARMS: dict[str, dict] = {
    # 0% recurve: bare workspace, task statement + empty solution.py. The agent
    # solves however it likes; exiting with a non-empty solution = declared done.
    "A0": {"recurve": False, "config": {}, "label": "0% recurve"},
    # 100% recurve: the same workspace, recurve-init'd. The agent must express the
    # task as a claim with a RED-first probe it authors + at least one trap, then
    # burn down until `recurve matrix --gate` is green. Gate green = declared done.
    "A3": {"recurve": True, "config": {}, "label": "100% recurve"},
}


def arm_names() -> list[str]:
    return list(_ARMS)


def arm_spec(name: str) -> dict:
    """Return the workspace spec for an arm. Raises KeyError on an unknown arm —
    an experiment naming an arm that does not exist fails loud, before any run."""
    if name not in _ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {', '.join(_ARMS)}")
    return dict(_ARMS[name])
