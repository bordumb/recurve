"""off: the no-op adversary — always no_objection (today's default
behavior, `docs/plans/ablation-infra.md` §3)."""
from __future__ import annotations

from recurvelib.loop.reviewers import AdversaryVerdict


class NoOpAdversary:
    def review(self, claim) -> AdversaryVerdict:
        return AdversaryVerdict.no_objection()
