"""The concrete Governor adapters (`docs/plans/ablation-infra.md` §3, AI2/AI6)."""
from __future__ import annotations

from recurvelib.adapters.governor.off import NoOpGovernor
from recurvelib.adapters.governor.mechanical import MechanicalGovernor
from recurvelib.adapters.governor.mechanical_review import MechanicalReviewGovernor
from recurvelib.adapters.governor.human_required import HumanRequiredGovernor
from recurvelib.adapters.registry import build_governor_registry

GOVERNOR_ADAPTERS = build_governor_registry({
    "off": NoOpGovernor,
    "mechanical": MechanicalGovernor,
    "mechanical_review": MechanicalReviewGovernor,
    "human_required": HumanRequiredGovernor,
})
