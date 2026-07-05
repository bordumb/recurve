"""arms.py — arm name → workspace spec (pure).

An arm is how a cell is set up before the agent runs. The mapping is a pure
function so the matrix stays data: adding an arm is a table entry, not new code.
The arm names A0/A3 come from the full program's arm matrix (eval-full.md).

A7-A10 (docs/plans/oracle-strength-and-decorrelation.md §3a) resolve their
`adversary=`/`governor=` config through recurvelib's OWN adapter registry —
imported here, never reimplemented (docs/plans/ablation-infra.md AI5): this
module and `/recurve-work`'s own gate config are two callers of one
implementation, exactly like `AGENT_CMD` already serves both today. `eval/`
stays a separate uv project (recurvelib is stdlib+PyYAML); the dependency is
one-directional — `eval` imports `recurvelib`, never the reverse.
"""

from __future__ import annotations

import sys
from pathlib import Path

# eval/evallib/arms.py -> eval/evallib -> eval -> the repo root, where
# recurvelib/ lives. recurvelib is not pip-installed under this project (see
# pyproject.toml's stdlib+PyYAML posture); this is the one-directional bridge.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from recurvelib.adapters.adversary import ADVERSARY_ADAPTERS  # noqa: E402
from recurvelib.adapters.governor import GOVERNOR_ADAPTERS  # noqa: E402

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
    # A7-A10: E4/ablation-phase arms (not POC arms — the POC keeps {A0, A3}
    # unchanged). Each extends A3 by one or two switches, per the PRD's own
    # ladder-not-factorial design (§3a): marginal detection per layer before
    # measuring the combination.
    "A7": {"recurve": True, "config": {"adversary": "cross_model"},
           "label": "A3 + adversary=cross_model"},
    "A8": {"recurve": True, "config": {"governor": "mechanical"},
           "label": "A3 + governor=mechanical"},
    "A9": {"recurve": True, "config": {"governor": "mechanical_review"},
           "label": "A3 + governor=mechanical_review"},
    "A10": {"recurve": True, "config": {"adversary": "cross_model", "governor": "mechanical_review"},
            "label": "A3 + adversary=cross_model + governor=mechanical_review"},
}


def arm_names() -> list[str]:
    return list(_ARMS)


def arm_spec(name: str) -> dict:
    """Return the workspace spec for an arm. Raises KeyError on an unknown arm —
    an experiment naming an arm that does not exist fails loud, before any run."""
    if name not in _ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {', '.join(_ARMS)}")
    return dict(_ARMS[name])


def resolve_adversary_adapter(name: str):
    """Resolve an arm's `adversary=` config value through recurvelib's OWN
    registry — never a local reimplementation."""
    from recurvelib.adapters.registry import resolve_adversary
    return resolve_adversary(name, ADVERSARY_ADAPTERS)


def resolve_governor_adapter(name: str):
    """Resolve an arm's `governor=` config value through recurvelib's OWN
    registry — never a local reimplementation."""
    from recurvelib.adapters.registry import resolve_governor
    return resolve_governor(name, GOVERNOR_ADAPTERS)
