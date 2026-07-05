# A broken HumanRequiredGovernor that verifies the signature and the
# identity type, but never checks that the signed cycle_snapshot_hash
# matches the CURRENT snapshot — an approval of an OLD snapshot silently
# clears a DRIFTED one. The exact replay/drift bug AI6 exists to prevent.
import json
from pathlib import Path

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.adapters._shared.identity import is_human_identity


class BrokenHumanRequiredGovernor:
    def __init__(self, attestations_dir, verify_fn):
        self.attestations_dir = Path(attestations_dir)
        self.verify_fn = verify_fn

    def audit(self, cycle):
        # BUG: reads ANY attestation file present, regardless of hash match.
        files = list(self.attestations_dir.glob("*.json"))
        if not files:
            return GovernorVerdict.pending_human_signoff()
        att = json.loads(files[0].read_text())
        identity = att.get("identity", {})
        payload = att.get("payload", {})
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        if not self.verify_fn(payload_bytes, att.get("signature", ""), identity.get("public_key", "")):
            return GovernorVerdict.pending_human_signoff()
        if not is_human_identity(identity):
            return GovernorVerdict.pending_human_signoff()
        # BUG: no cycle_snapshot_hash comparison at all.
        if payload.get("decision") == "approve":
            return GovernorVerdict.cleared()
        return GovernorVerdict.veto({cid: payload.get("rationale", "") for cid in cycle.claim_ids})
