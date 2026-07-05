"""arms.py — arm name -> ArmSpec, the tuple of port selections that IS an arm (pure).

An arm varies along six independent axes — Workspace, Done-signal, Boundary,
Audit, Adversary, Governor — and nothing else. `ArmSpec` (one field per axis)
replaces the old flat `{"recurve": bool, "config": dict}` shape, which only
fit two of the six. Adding an arm is a new `ArmSpec` literal; adding a new
axis later is a new, DEFAULTED field, never an edit to an existing arm's
literal.

A7-A10 (docs/plans/oracle-strength-and-decorrelation.md §3a) resolve their
`adversary=`/`governor=` config through recurvelib's OWN adapter registry —
imported here, never reimplemented (docs/plans/ablation-infra.md AI5).
`boundary=` is a third recurvelib-owned axis (`enforced` default | the
deliberately dangerous `open`), resolved the same way. `eval/` stays a
separate uv project (recurvelib is stdlib+PyYAML); the dependency is
one-directional — `eval` imports `recurvelib`, never the reverse.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path

# eval/evallib/arms.py -> eval/evallib -> eval -> the repo root, where
# recurvelib/ lives. recurvelib is not pip-installed under this project (see
# pyproject.toml's stdlib+PyYAML posture); this is the one-directional bridge.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from recurvelib.adapters.adversary import ADVERSARY_ADAPTERS  # noqa: E402
from recurvelib.adapters.governor import GOVERNOR_ADAPTERS  # noqa: E402
from recurvelib.adapters.boundary import BOUNDARY_ADAPTERS  # noqa: E402


@dataclass(frozen=True)
class ArmSpec:
    """An arm is a TUPLE OF PORT SELECTIONS — nothing else. Six axes:

      workspace   — WorkspacePort:   "bare" | "recurve_init"
      done_signal — DoneSignalPort:  "gate" | "self_report" | "external_ci"
      boundary    — BoundaryPort:    "enforced" | "open"            (recurvelib)
      audit       — AuditPort:       "none" | "drill_hardened"
      adversary   — AdversaryPort:   "off" | "same_model" | "cross_model"   (recurvelib, existing)
      governor    — GovernorPort:    "off" | "mechanical" | "mechanical_review" | "human_required" (recurvelib, existing)

    `boundary`/`audit`/`adversary`/`governor` default to the inert value, so
    an existing arm literal never has to name axes it doesn't use — arms
    that only need workspace/done_signal stay byte-identical across every
    later addition, because they all resolve to the same defaults.
    """

    workspace: str
    done_signal: str
    boundary: str = "enforced"
    audit: str = "none"
    adversary: str = "off"
    governor: str = "off"
    # The shell command DoneSignalPort["external_ci"] runs; meaningful only
    # when done_signal == "external_ci" (validated there, not here — an arm
    # not using that port pays nothing for the field it left blank).
    external_ci_command: str = ""
    label: str = ""

    @property
    def recurve(self) -> bool:
        """True iff the workspace is recurve-init'd. A derived property, not
        an independent field — `workspace` is the one source of truth, so
        `recurve` can never drift from it independently."""
        return self.workspace == "recurve_init"


# A3: 100% recurve, full discipline, every other axis at its default.
_A3 = ArmSpec(workspace="recurve_init", done_signal="gate", label="100% recurve")

_ARMS: dict[str, ArmSpec] = {
    # 0% recurve: bare workspace, task statement + empty solution.py. The agent
    # solves however it likes; exiting with a non-empty solution = declared done.
    # DoneSignalPort["self_report"] — see A6 below for its sibling.
    "A0": ArmSpec(workspace="bare", done_signal="self_report", label="0% recurve"),
    # 100% recurve: the same workspace, recurve-init'd. The agent must express the
    # task as a claim with a RED-first probe it authors + at least one trap, then
    # burn down until `recurve matrix --gate` is green. Gate green = declared done.
    "A3": _A3,
    # A3's workspace (a real ledger IS present), but done_signal="self_report"
    # — the SAME port A0 uses, not a bespoke "ignore the gate" special case:
    # a real ledger existing in the workspace has zero effect on the
    # declared-done decision under this port.
    "A6": replace(_A3, done_signal="self_report", label="A3, controller off"),
    # A7-A10: ablation-phase arms (not POC arms — the POC keeps {A0, A3}
    # unchanged). Each extends A3 by one or two switches: marginal detection
    # per layer before measuring the combination.
    "A7": replace(_A3, adversary="cross_model", label="A3 + adversary=cross_model"),
    "A8": replace(_A3, governor="mechanical", label="A3 + governor=mechanical"),
    "A9": replace(_A3, governor="mechanical_review", label="A3 + governor=mechanical_review"),
    "A10": replace(_A3, adversary="cross_model", governor="mechanical_review",
                   label="A3 + adversary=cross_model + governor=mechanical_review"),
}


def arm_names() -> list[str]:
    return list(_ARMS)


def arm_spec(name: str) -> ArmSpec:
    """Return the named arm's ArmSpec. Raises KeyError on an unknown arm —
    an experiment naming an arm that does not exist fails loud, before any run."""
    if name not in _ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {', '.join(_ARMS)}")
    return _ARMS[name]


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


def resolve_boundary_adapter(name: str):
    """Resolve an arm's `boundary=` value through recurvelib's OWN registry —
    never a local reimplementation. The one resolution this module treats as
    inherently dangerous when `name == "open"`."""
    from recurvelib.adapters.registry import resolve_boundary
    return resolve_boundary(name, BOUNDARY_ADAPTERS)
