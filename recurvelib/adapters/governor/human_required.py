"""human_required: async, cryptographically-attested human sign-off
(`docs/plans/ablation-infra.md` AI6 — pre-launch simplification: async
verdict state).

Human review is asynchronous by nature, so `audit()` cannot block the loop
waiting for it: with no attestation yet, it returns
`GovernorVerdict.pending_human_signoff()` and the calling loop suspends
cleanly (it must not busy-wait). A separate act — production: `recurve
governor approve <claim_id> --attestation <path>`; here:
`write_attestation` — resumes it. The attestation is a signed envelope over
`{cycle_snapshot_hash, claim_ids, decision, rationale}`, bound to the exact
reviewed artifact by its content hash, and it must be signed by a
human-attested identity (`_shared.identity.is_human_identity`), never an
agent-attested one.

`verify_fn(payload_bytes, signature, public_key) -> bool` is the pluggable,
offline signature check — production deployments point this at
`auths_curve.integration.verify_bytes`/`verify_action_envelope` (already
shipped, reused unchanged, §5a); recurvelib itself never imports an identity
library directly, the same seam `[receipts] signer`/`verifier` already use.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.adapters._shared.identity import is_human_identity


def shell_verify_fn(verifier_cmd: str):
    """Wrap a configured shell command (`[gate] human_verifier`, the same
    seam shape `[receipts] verifier` already uses) into the
    `verify_fn(payload_bytes, signature, public_key) -> bool` shape this
    module needs: the command receives the payload bytes on stdin and the
    signature + public key as argv, and exits 0 iff the signature verifies.
    Shared by the `recurve governor approve` CLI and the live decide()
    wiring so there is one implementation of "run the configured verifier
    command", not two."""

    def verify(payload_bytes: bytes, signature: str, public_key: str) -> bool:
        try:
            r = subprocess.run(shlex.split(verifier_cmd) + [signature, public_key],
                              input=payload_bytes, capture_output=True, timeout=60)
        except Exception:
            return False
        return r.returncode == 0

    return verify


class AttestationError(Exception):
    """An attestation could not be verified — refused, never silently
    accepted at face value."""


def cycle_snapshot_hash(cycle) -> str:
    """A stable hash identifying exactly this cycle snapshot + claim set —
    what a human attestation must bind to. An approval of this hash can
    never clear a claim silently modified afterward (the replay/drift
    check): the hash changes the moment the underlying commit or claim set
    does."""
    h = hashlib.sha256()
    h.update(cycle.commit.encode())
    h.update(json.dumps(sorted(cycle.claim_ids), sort_keys=True).encode())
    return h.hexdigest()


def verify_attestation(att: dict, cycle, verify_fn) -> tuple[bool, str]:
    """Fail-closed, in order: (1) the payload's signature verifies under the
    claimed identity's public key; (2) the identity is human-attested, never
    agent-attested, even if the signature otherwise verifies; (3) the signed
    `cycle_snapshot_hash` matches the CURRENT snapshot exactly (an approval
    of v1 must not clear a claim silently modified to v2)."""
    identity = att.get("identity", {})
    payload = att.get("payload", {})
    signature = att.get("signature", "")
    public_key = identity.get("public_key", "")
    payload_bytes = json.dumps(payload, sort_keys=True).encode()

    try:
        verified = bool(verify_fn(payload_bytes, signature, public_key))
    except Exception as e:
        return False, f"verify_fn raised: {e}"
    if not verified:
        return False, "signature does not verify"
    if not is_human_identity(identity):
        return False, "signer is not a human-attested identity"
    if payload.get("cycle_snapshot_hash") != cycle_snapshot_hash(cycle):
        return False, "signed cycle_snapshot_hash does not match the current snapshot (drift)"
    return True, "ok"


class HumanRequiredGovernor:
    def __init__(self, attestations_dir, verify_fn):
        self.attestations_dir = Path(attestations_dir)
        self.verify_fn = verify_fn

    def audit(self, cycle) -> GovernorVerdict:
        att = self._read_attestation(cycle)
        if att is None:
            return GovernorVerdict.pending_human_signoff()
        ok, _reason = verify_attestation(att, cycle, self.verify_fn)
        if not ok:
            # A present-but-INVALID attestation must not resolve to either
            # cleared or veto on any default — it stays pending until a
            # verified one arrives. No default-approve, no default-reject.
            return GovernorVerdict.pending_human_signoff()
        payload = att["payload"]
        if payload.get("decision") == "approve":
            return GovernorVerdict.cleared()
        reason = payload.get("rationale") or "a human reviewer rejected this cycle"
        return GovernorVerdict.veto({cid: reason for cid in cycle.claim_ids})

    def _read_attestation(self, cycle) -> dict | None:
        p = self.attestations_dir / f"{cycle_snapshot_hash(cycle)}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text())


def write_attestation(
    attestations_dir, cycle, *, decision: str, rationale: str, identity: dict, sign_fn,
) -> Path:
    """The resume act (production: `recurve governor approve`): build the
    payload bound to this exact cycle snapshot, sign it with `sign_fn`
    (production: a human-attested identity's real key), and write it where
    `HumanRequiredGovernor` looks for it. `decision` is `"approve"` or
    `"reject"`."""
    if decision not in ("approve", "reject"):
        raise AttestationError(f"decision must be approve|reject, got {decision!r}")
    payload = {
        "cycle_snapshot_hash": cycle_snapshot_hash(cycle),
        "claim_ids": sorted(cycle.claim_ids),
        "decision": decision,
        "rationale": rationale,
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    signature = sign_fn(payload_bytes)
    att = {"identity": identity, "payload": payload, "signature": signature}
    d = Path(attestations_dir)
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{payload['cycle_snapshot_hash']}.json"
    out.write_text(json.dumps(att, sort_keys=True, indent=2))
    return out
