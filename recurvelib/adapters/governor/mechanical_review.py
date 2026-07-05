"""mechanical_review: a single decorrelated-model pass reviews the BATCH of
newly-green claims from the cycle — one review call per batch, not per
claim (R5's review tier, `docs/plans/ablation-infra.md` AI2). This is
precisely the scenario the O6 incident occurred in: an autonomous run,
nobody watching claim-by-claim. Reuses R2's isolation and
identity-verification machinery exactly.

The reviewer is a BYO command, same wire protocol shape as the adversary's:
it runs inside the isolated `CycleSnapshot` and prints one JSON verdict
naming its own actual `served_model`, plus `vetoes` — a `{claim_id: reason}`
mapping (empty means the whole batch clears).
"""
from __future__ import annotations

import json
import os

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.adapters._shared.reviewer_base import run_isolated_review
from recurvelib.adapters._shared.provenance import (
    Provenance, metadata_verified, unverified, verified_different_identity,
)


class GovernorReviewerError(Exception):
    """The configured governor reviewer command failed, or its output didn't
    follow the wire protocol."""


class GovernorIdentityViolation(GovernorReviewerError):
    """The review-tier pass's verified served identity does not verifiably
    differ from the cycle's own claim-authoring identity — refused from
    clearing `governor_cleared`, never silently accepted."""


def _cmd(explicit: str | None) -> list[str]:
    cmd = explicit or os.environ.get("RECURVE_GOVERNOR_CMD")
    if not cmd:
        raise GovernorReviewerError(
            "no governor reviewer command configured (RECURVE_GOVERNOR_CMD, or cmd=) — "
            "mechanical_review never silently falls back to the main loop's AGENT_CMD; the "
            "governor must be demonstrably configured, not assumed distinct")
    return cmd.split()


class MechanicalReviewGovernor:
    """`actor_provenance` is the cycle's own claim-authoring identity (already
    established) — required so this tier has something to verify difference
    against, same as `CrossModelAdversary`."""

    def __init__(self, actor_provenance: Provenance, *, cmd: str | None = None, timeout: int = 300):
        self.actor_provenance = actor_provenance
        self.cmd = cmd
        self.timeout = timeout
        self.last_provenance: Provenance | None = None

    def audit(self, cycle) -> GovernorVerdict:
        inv = run_isolated_review(cycle, _cmd(self.cmd), timeout=self.timeout)
        if inv.returncode != 0:
            raise GovernorReviewerError(f"governor reviewer exited {inv.returncode}: {inv.stderr[:200]}")
        try:
            payload = json.loads(inv.stdout.strip() or "{}")
        except json.JSONDecodeError as e:
            raise GovernorReviewerError(f"governor reviewer output was not valid JSON: {e}") from e
        served = payload.get("served_model")
        prov = metadata_verified(served) if served else unverified()
        self.last_provenance = prov
        if not verified_different_identity(self.actor_provenance, prov):
            raise GovernorIdentityViolation(
                f"review-tier's verified served identity ({prov.identity!r}, strength="
                f"{prov.strength.value}) does not verifiably differ from the cycle's "
                f"claim-authoring identity ({self.actor_provenance.identity!r}, strength="
                f"{self.actor_provenance.strength.value}) — refused from clearing "
                f"governor_cleared")
        vetoes = payload.get("vetoes") or {}
        if vetoes:
            return GovernorVerdict.veto(dict(vetoes))
        return GovernorVerdict.cleared()
