# A broken HumanRequiredGovernor that verifies the signature and the
# cycle_snapshot_hash binding, but never checks that the signer is
# human-attested — an agent-signed attestation silently clears the cycle.
import hashlib
import json
from pathlib import Path


def _hash(cycle):
    h = hashlib.sha256()
    h.update(cycle.commit.encode())
    h.update(json.dumps(sorted(cycle.claim_ids), sort_keys=True).encode())
    return h.hexdigest()


class BrokenHumanRequiredGovernor:
    def __init__(self, attestations_dir, verify_fn):
        self.attestations_dir = Path(attestations_dir)
        self.verify_fn = verify_fn

    def audit(self, cycle):
        from recurvelib.loop.reviewers import GovernorVerdict
        p = self.attestations_dir / f"{_hash(cycle)}.json"
        if not p.exists():
            return GovernorVerdict.pending_human_signoff()
        att = json.loads(p.read_text())
        identity = att.get("identity", {})
        payload = att.get("payload", {})
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        if not self.verify_fn(payload_bytes, att.get("signature", ""), identity.get("public_key", "")):
            return GovernorVerdict.pending_human_signoff()
        # BUG: no is_human_identity check at all — an agent-signed
        # attestation is accepted just as readily as a human one.
        if payload.get("decision") == "approve":
            return GovernorVerdict.cleared()
        return GovernorVerdict.veto({cid: payload.get("rationale", "") for cid in cycle.claim_ids})
