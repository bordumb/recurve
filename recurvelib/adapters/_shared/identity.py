"""Identity-type checks: human vs. agent, by POSITIVE capability attestation
(`docs/plans/ablation-infra.md` AI6/§5a).

Deliberately origin-agnostic: this module knows nothing about any specific
identity system (KERI, did:key, or otherwise) — an "identity" here is just a
mapping carrying a `capability` field. Production deployments back this with
a real cryptographic identity (this workspace's sibling `auths-curve`
project already ships `mint_agent`/`is_agent_identity`, built for signing
recurve's own gate verdicts — directly reusable, not reinvented); the seam
this module exposes is the same shape `[receipts] signer`/`verifier` already
use (a pluggable, external verification function), so recurvelib itself
never imports an identity library directly.

A POSITIVE capability check (`is_human_identity`) rather than the mere
ABSENCE of an agent one — presence checks are harder to spoof than absence
checks, the same principle behind R1's anti-gaming traps.
"""
from __future__ import annotations

AGENT_CAPABILITY = "agent"
HUMAN_CAPABILITY = "human_signoff"


def _has_capability(identity: dict, capability: str) -> bool:
    cap = identity.get("capability")
    if isinstance(cap, str):
        return cap == capability
    if isinstance(cap, (list, tuple, set)):
        return capability in cap
    return False


def is_agent_identity(identity: dict) -> bool:
    """True iff this identity carries a positive agent capability
    attestation. Mirrors `auths_curve.integration.is_agent_identity`'s
    shape."""
    return _has_capability(identity, AGENT_CAPABILITY)


def is_human_identity(identity: dict) -> bool:
    """True iff this identity carries a positive HUMAN capability
    attestation — never merely "not an agent." A script cannot forge "a
    human looked at this" by minting itself a key with no capability at
    all; absence of `agent` is not evidence of `human_signoff`."""
    return _has_capability(identity, HUMAN_CAPABILITY)
