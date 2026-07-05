"""Uniform provenance: every port, not just adversary/governor; two tiers of
strength (`docs/plans/ablation-infra.md` AI7).

Closes the asymmetry where R2/R5 verify the adversary/governor's identity
AGAINST the actor's logged identity, while the actor's own identity was
never itself held to the same standard — `Actor`, `Adversary`, and
`Governor` all attach a `Provenance` alongside their result. Two strengths,
chosen per adapter: `metadata_verified` (the served-model field from the
provider's own API response — cheap, the R2/R5 default) and
`cryptographically_attested` (an auths-signed envelope — required for
`human_required`, an available upgrade for the automated tiers).
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Callable


class ProvenanceStrength(str, Enum):
    UNVERIFIED = "unverified"                    # no identity check performed (AI11 placeholder)
    METADATA_VERIFIED = "metadata_verified"       # the served-model field, from the provider's own response
    CRYPTOGRAPHICALLY_ATTESTED = "cryptographically_attested"   # an auths-signed envelope, offline-verifiable


@dataclasses.dataclass(frozen=True)
class Provenance:
    """`identity` is whatever this strength verifies: a served-model name for
    `metadata_verified`, a signer DID for `cryptographically_attested`. A
    claimed cryptographic tier that fails to verify is represented here as
    `UNVERIFIED` with `verify_error` set — never silently accepted at its
    claimed strength."""

    strength: ProvenanceStrength
    identity: str | None
    envelope: str | None = None
    verify_error: str | None = None

    @property
    def is_verified(self) -> bool:
        return self.strength is not ProvenanceStrength.UNVERIFIED and self.verify_error is None


def unverified(identity: str | None = None) -> Provenance:
    return Provenance(strength=ProvenanceStrength.UNVERIFIED, identity=identity)


def metadata_verified(identity: str) -> Provenance:
    """The default, cheap strength: `identity` came from the provider's own
    API response metadata (the served model), not a self-reported flag."""
    return Provenance(strength=ProvenanceStrength.METADATA_VERIFIED, identity=identity)


def cryptographically_attested(
    identity: str, envelope: str, verify_fn: Callable[[str, str], bool],
) -> Provenance:
    """Build a `cryptographically_attested` provenance — but only if
    `verify_fn(envelope, identity)` actually verifies. AI7's anti-gaming
    trap: a verification failure demotes to `UNVERIFIED` with `verify_error`
    recorded, never silently accepted at the claimed strength."""
    try:
        ok = bool(verify_fn(envelope, identity))
    except Exception as e:  # a raising verifier is a failed verification, not a crash
        return Provenance(strength=ProvenanceStrength.UNVERIFIED, identity=identity,
                          envelope=envelope, verify_error=str(e))
    if not ok:
        return Provenance(strength=ProvenanceStrength.UNVERIFIED, identity=identity,
                          envelope=envelope, verify_error="signature did not verify")
    return Provenance(strength=ProvenanceStrength.CRYPTOGRAPHICALLY_ATTESTED, identity=identity,
                      envelope=envelope)


def verified_different_identity(a: Provenance, b: Provenance) -> bool:
    """R2/R5's identity-verification requirement, in one place: True iff BOTH
    provenances are actually verified (not unverified, not demoted by a
    failed signature) AND their identities differ. A same-served-model
    adversary, or an adversary signing with the actor's own key, fails this
    — which is exactly the refusal R2/R5 require."""
    if not (a.is_verified and b.is_verified):
        return False
    return a.identity != b.identity
