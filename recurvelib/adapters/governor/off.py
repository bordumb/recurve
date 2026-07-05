"""off: the no-op governor — always cleared (`docs/plans/ablation-infra.md`
§3). Not the suite-wide default (AI10 makes `mechanical` the default) — an
explicit opt-out."""
from __future__ import annotations

from recurvelib.loop.reviewers import GovernorVerdict


class NoOpGovernor:
    def audit(self, cycle) -> GovernorVerdict:
        return GovernorVerdict.cleared()
