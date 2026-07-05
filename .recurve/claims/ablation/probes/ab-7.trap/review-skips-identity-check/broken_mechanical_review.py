# A broken mechanical_review governor that never checks identity — it
# accepts whatever the reviewer says even when the reviewer's served_model
# matches the cycle's own claim-authoring identity. This is the O6 shape at
# the run level: a correlated blind spot, unchallenged.
import json

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.adapters.governor.mechanical_review import _cmd


class BrokenMechanicalReviewGovernor:
    def __init__(self, actor_provenance, *, cmd=None, timeout=300):
        self.actor_provenance = actor_provenance
        self.cmd = cmd
        self.timeout = timeout

    def audit(self, cycle):
        from recurvelib.adapters._shared.reviewer_base import run_isolated_review
        inv = run_isolated_review(cycle, _cmd(self.cmd), timeout=self.timeout)
        payload = json.loads(inv.stdout.strip() or "{}")
        # BUG: no identity check at all.
        vetoes = payload.get("vetoes") or {}
        if vetoes:
            return GovernorVerdict.veto(dict(vetoes))
        return GovernorVerdict.cleared()
