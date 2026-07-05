#!/usr/bin/env bash
# AB-11: human_required governance, cryptographically attested — the async
# pending_human_signoff state machine (docs/plans/ablation-infra.md AI6).
# RED-first: until recurvelib.adapters.governor.human_required exists the
# probe is RED.
#
# Honest limit (see the Gap's oracle_waiver): this is an unattended,
# autonomous process. It cannot physically tap Touch ID, so it cannot
# exercise auths-core's real Secure-Enclave-gated signer
# (crates/auths-core/src/storage/secure_enclave.rs) end to end. Everything
# UP TO that boundary is proven for real here with a MOCKED human-attested
# signer: a real Ed25519 keypair and a real signature over a real payload
# (via the `cryptography` package), explicitly labeled as a test double
# standing in for auths-core's biometric-gated key. What this probe does
# NOT claim: that a live biometric prompt was tested.
#
# With $TRAP_FIXTURE: a scenario naming a gaming attempt against the
# verifier (replay/drift, or an agent-attested signature masquerading as
# human). The real engine must refuse (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import json
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from recurvelib.adapters._shared.identity import is_human_identity, is_agent_identity
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.governor.human_required import (
        HumanRequiredGovernor, write_attestation, cycle_snapshot_hash,
        verify_attestation, AttestationError,
    )
except ImportError:
    print("ours=no recurvelib.adapters.governor.human_required yet "
          "oracle=the async pending_human_signoff state machine")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


class _Cycle:
    def __init__(self, commit, claim_ids):
        self.commit = commit
        self.claim_ids = tuple(claim_ids)


# --- a REAL Ed25519 keypair, mocking ONLY where the key lives (never real
# biometric hardware) — the signature/verification machinery is genuine. ---

def keypair():
    sk = ed25519.Ed25519PrivateKey.generate()
    pk = sk.public_key()
    pk_hex = pk.public_bytes_raw().hex()
    return sk, pk_hex


def sign_fn_for(sk):
    def sign(payload_bytes: bytes) -> str:
        return sk.sign(payload_bytes).hex()
    return sign


def verify_fn(payload_bytes: bytes, signature: str, public_key: str) -> bool:
    try:
        pk = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
        pk.verify(bytes.fromhex(signature), payload_bytes)
        return True
    except Exception:
        return False


human_sk, human_pk = keypair()
agent_sk, agent_pk = keypair()
human_identity = {"capability": "human_signoff", "public_key": human_pk, "who": "a-human-reviewer"}
agent_identity = {"capability": "agent", "public_key": agent_pk, "who": "an-agent-identity"}

cycle = _Cycle("a" * 40, ["X-1", "X-2"])

if fixture:
    import importlib.util

    scenario = (Path(fixture) / "scenario").read_text().strip()

    if scenario == "replay_drift_not_refused":
        spec = importlib.util.spec_from_file_location(
            "bhr1", Path(fixture) / "broken_human_required.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d = Path(tempfile.mkdtemp(prefix="ab11-att-"))
        write_attestation(d, cycle, decision="approve", rationale="looks good",
                          identity=human_identity, sign_fn=sign_fn_for(human_sk))
        drifted_cycle = _Cycle("b" * 40, ["X-1", "X-2"])  # the underlying commit changed
        gov = mod.BrokenHumanRequiredGovernor(d, verify_fn)
        v = gov.audit(drifted_cycle)
        if v.is_clear:
            print("ours=an approval of the OLD snapshot cleared a DRIFTED one "
                  "oracle=must stay pending — correctly caught the replay/drift bug")
            sys.exit(1)
        print("ours=the broken governor still stayed pending oracle=expected it to clear "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)

    if scenario == "agent_identity_masquerades_as_human":
        spec = importlib.util.spec_from_file_location(
            "bhr2", Path(fixture) / "broken_human_required.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d = Path(tempfile.mkdtemp(prefix="ab11-att-"))
        write_attestation(d, cycle, decision="approve", rationale="an agent, not a human, signed this",
                          identity=agent_identity, sign_fn=sign_fn_for(agent_sk))
        gov = mod.BrokenHumanRequiredGovernor(d, verify_fn)
        v = gov.audit(cycle)
        if v.is_clear:
            print("ours=an agent-signed attestation cleared the cycle "
                  "oracle=must stay pending — correctly caught the identity-type bug")
            sys.exit(1)
        print("ours=the broken governor still stayed pending oracle=expected it to clear "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. is_human_identity requires a POSITIVE human capability — never merely
# "not agent".
check("a human-capability identity is human", is_human_identity(human_identity) is True)
check("an agent-capability identity is not human", is_human_identity(agent_identity) is False)
check("an identity with no capability at all is neither human nor agent",
      is_human_identity({}) is False and is_agent_identity({}) is False)

# 2. with NO attestation on disk yet, audit() returns pending_human_signoff —
# the loop suspends cleanly rather than busy-waiting.
d1 = Path(tempfile.mkdtemp(prefix="ab11-empty-"))
gov1 = HumanRequiredGovernor(d1, verify_fn)
v1 = gov1.audit(cycle)
check("no attestation -> pending, not cleared, not vetoed", v1.pending is True and v1.is_clear is False)

# 3. a genuine human approval, bound to THIS exact snapshot, clears.
d2 = Path(tempfile.mkdtemp(prefix="ab11-approve-"))
out = write_attestation(d2, cycle, decision="approve", rationale="independently re-derived, correct",
                        identity=human_identity, sign_fn=sign_fn_for(human_sk))
check("write_attestation writes a real file", out.exists())
gov2 = HumanRequiredGovernor(d2, verify_fn)
v2 = gov2.audit(cycle)
check("a verified human approval clears the cycle", v2.is_clear is True)

# 4. a genuine human REJECTION vetoes with the rationale — never a bare
# rejection.
d3 = Path(tempfile.mkdtemp(prefix="ab11-reject-"))
write_attestation(d3, cycle, decision="reject", rationale="contradicts the published result",
                  identity=human_identity, sign_fn=sign_fn_for(human_sk))
gov3 = HumanRequiredGovernor(d3, verify_fn)
v3 = gov3.audit(cycle)
check("a verified human rejection vetoes with the rationale",
      v3.is_clear is False and all("contradicts" in r for r in v3.vetoes.values()))

# 5. a forged signature (tampered payload after signing) never clears —
# demoted, stays pending, never silently accepted.
d4 = Path(tempfile.mkdtemp(prefix="ab11-forged-"))
out4 = write_attestation(d4, cycle, decision="approve", rationale="ok",
                         identity=human_identity, sign_fn=sign_fn_for(human_sk))
att = json.loads(out4.read_text())
att["payload"]["decision"] = "approve"
att["payload"]["rationale"] = "TAMPERED AFTER SIGNING"  # the signature no longer covers this
out4.write_text(json.dumps(att))
gov4 = HumanRequiredGovernor(d4, verify_fn)
v4 = gov4.audit(cycle)
check("a tampered attestation never clears", v4.is_clear is False and v4.pending is True)

# 6. verify_attestation never auto-resolves on any timeout/cap/default — it
# is checked fresh every audit() call; repeated calls with no new
# attestation stay pending, never flip to cleared or veto on their own.
v1_again = gov1.audit(cycle)
check("repeated audits with no attestation stay pending forever, never auto-resolve",
      v1_again.pending is True)

print("human_required's async state machine is real: pending with no attestation, cleared/"
      "vetoed on a verified human signature bound to this exact snapshot, demoted (never "
      "accepted) on a forged or tampered one. Mocked ONLY where the key lives (a real "
      "Ed25519 keypair standing in for auths-core's Secure-Enclave-gated one) — the "
      "signature/verification machinery, and the identity-type discrimination, are real.")
sys.exit(0)
PYEOF
