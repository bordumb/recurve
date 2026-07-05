#!/usr/bin/env bash
# AB-5: uniform provenance across every port, two tiers of strength
# (docs/plans/ablation-infra.md AI7). RED-first: until
# recurvelib.adapters._shared.provenance exists the probe is RED.
#
# With $TRAP_FIXTURE: a scenario naming a gaming attempt — a forged/failed
# signature claiming cryptographically_attested, or an adversary signing with
# the actor's own key. The real engine must demote/refuse (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    pass
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters._shared.provenance import (
        Provenance, ProvenanceStrength, unverified, metadata_verified,
        cryptographically_attested, verified_different_identity,
    )
except ImportError:
    print("ours=no recurvelib.adapters._shared.provenance yet "
          "oracle=Actor/Adversary/Governor all carry a uniform, two-tier provenance")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


def always_true(envelope, identity):
    return True


def always_false(envelope, identity):
    return False


def raises(envelope, identity):
    raise ValueError("malformed envelope")


if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()

    if scenario == "forged_envelope_claims_attested":
        # A verifier that correctly rejects a forged envelope must demote —
        # never silently accept the claimed cryptographically_attested tier.
        p = cryptographically_attested("did:example:forger", "forged-envelope", always_false)
        if p.strength is ProvenanceStrength.CRYPTOGRAPHICALLY_ATTESTED:
            print("ours=forged envelope accepted as cryptographically_attested "
                  "oracle=must demote to unverified (gaming claim succeeded)")
            sys.exit(0)
        print(f"a failed verification demotes to {p.strength.value}, verify_error={p.verify_error!r}")
        sys.exit(1)

    if scenario == "adversary_signs_with_actors_key":
        # R2/R5's identity check: an adversary whose provenance identity
        # equals the actor's must not count as a verified-different identity,
        # even if both individually verify.
        actor_prov = metadata_verified("claude-sonnet-5")
        adversary_prov = metadata_verified("claude-sonnet-5")  # same served identity
        if verified_different_identity(actor_prov, adversary_prov):
            print("ours=same-identity pair counted as verified-different "
                  "oracle=must be refused (gaming claim succeeded)")
            sys.exit(0)
        print("verified_different_identity correctly refuses a same-identity pair")
        sys.exit(1)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. unverified is the honest default (AI11's pre-AI7 placeholder shape).
u = unverified()
check("unverified is not verified", u.is_verified is False)

# 2. metadata_verified: cheap, identity-carrying, verified.
mv = metadata_verified("claude-sonnet-5")
check("metadata_verified is verified", mv.is_verified is True)
check("metadata_verified carries the identity", mv.identity == "claude-sonnet-5")

# 3. cryptographically_attested succeeds only when verify_fn actually verifies.
ok = cryptographically_attested("did:example:signer", "real-envelope", always_true)
check("a verifying envelope reaches cryptographically_attested",
      ok.strength is ProvenanceStrength.CRYPTOGRAPHICALLY_ATTESTED and ok.is_verified)

# 4. a failing verifier demotes to unverified, with the reason recorded.
bad = cryptographically_attested("did:example:signer", "bad-envelope", always_false)
check("a non-verifying envelope demotes to unverified", bad.strength is ProvenanceStrength.UNVERIFIED)
check("the demotion records why", bool(bad.verify_error))

# 5. a raising verifier (malformed envelope) also demotes, never crashes the caller.
crashed = cryptographically_attested("did:example:signer", "malformed", raises)
check("a raising verifier demotes rather than propagating", crashed.strength is ProvenanceStrength.UNVERIFIED)

# 6. verified_different_identity: the R2/R5 primitive.
a = metadata_verified("model-a")
b = metadata_verified("model-b")
check("two verified, distinct identities pass", verified_different_identity(a, b) is True)
check("the same identity twice fails", verified_different_identity(a, metadata_verified("model-a")) is False)
check("an unverified party never counts as distinct", verified_different_identity(a, unverified()) is False)

# 7. reviewer_base attaches Provenance uniformly (Actor/Adversary/Governor —
# here proven via the one code path already wired, run_claim_reviewer).
import subprocess
import tempfile
from recurvelib.adapters._shared.reviewer_base import run_claim_reviewer
d = Path(tempfile.mkdtemp(prefix="ab5-repo-"))
subprocess.run(["git", "init", "-q"], cwd=d, check=True)
empty_hooks = Path(tempfile.mkdtemp(prefix="ab5-nohooks-"))
subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
(d / "f.txt").write_text("x\n")
subprocess.run(["git", "add", "-A"], cwd=d, check=True)
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                "commit", "-q", "--no-gpg-sign", "-m", "i"], cwd=d, check=True)
inv = run_claim_reviewer(d, "HEAD", "X-1", ["true"], identity="claude-sonnet-5")
check("run_claim_reviewer attaches a metadata_verified provenance when given an identity",
      inv.provenance.strength is ProvenanceStrength.METADATA_VERIFIED
      and inv.provenance.identity == "claude-sonnet-5")

print("provenance is uniform across ports, two strengths, and a failed/forged cryptographic "
      "claim demotes rather than silently accepting — the R2/R5 identity check "
      "(verified_different_identity) refuses a same-identity or unverified pair")
sys.exit(0)
PYEOF
