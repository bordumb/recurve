"""The concrete Adversary adapters (`docs/plans/ablation-infra.md` §3, AI2)."""
from __future__ import annotations

from recurvelib.adapters.adversary.off import NoOpAdversary
from recurvelib.adapters.adversary.same_model import SameModelAdversary
from recurvelib.adapters.adversary.cross_model import CrossModelAdversary
from recurvelib.adapters.registry import build_adversary_registry

ADVERSARY_ADAPTERS = build_adversary_registry({
    "off": NoOpAdversary,
    "same_model": SameModelAdversary,
    "cross_model": CrossModelAdversary,
})
