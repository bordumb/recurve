"""Policy resolution: the suite-wide `[gate] governor=` default versus a
claim's own floor (`docs/plans/ablation-infra.md` AI9), and the mechanical
tier's default-on posture (AI10).

Floors compose by max-strength only: a claim's `min_governor_tier` holds
regardless of a WEAKER suite-wide default, but never weakens a STRONGER one.
A claim with no floor uses the suite default exactly — no behavior change
for the common case.
"""
from __future__ import annotations

ADVERSARY_TIERS = ("off", "same_model", "cross_model")
GOVERNOR_TIERS = ("off", "mechanical", "mechanical_review", "human_required")

_GOVERNOR_RANK = {t: i for i, t in enumerate(GOVERNOR_TIERS)}

# AI10: pre-launch, there is no existing deployment whose behavior this would
# change, and the cost is zero (re-execution of existing work, no new agent
# calls) — so the suite-wide governor default is "mechanical", not "off".
DEFAULT_GOVERNOR_TIER = "mechanical"
DEFAULT_ADVERSARY_TIER = "off"


class InvalidTierError(ValueError):
    """A configured or claim-floored tier isn't one of the known values."""


def effective_governor_tier(suite_default: str, min_governor_tier: str = "") -> str:
    """AI9: the tier a claim's governor check actually resolves to — at
    LEAST `min_governor_tier` (a claim-level floor), possibly stronger if
    the suite-wide default is stronger, but never weaker than the floor."""
    for tier in (suite_default, min_governor_tier):
        if tier and tier not in _GOVERNOR_RANK:
            raise InvalidTierError(f"unknown governor tier {tier!r}; known: {', '.join(GOVERNOR_TIERS)}")
    if not min_governor_tier:
        return suite_default
    if not suite_default:
        return min_governor_tier
    return max(suite_default, min_governor_tier, key=_GOVERNOR_RANK.get)
