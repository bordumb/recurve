"""cross_model: isolated review + verified-different-model check (R2,
`docs/plans/ablation-infra.md` §2). Same wire protocol as `same_model`; the
run additionally refuses when the adversary pass's VERIFIED served model
matches the actor's — checked from response metadata, not the requested
`--model` flag (the exact bug class that let the O6 incident through
unchallenged, plus the config-drift case where the flag says one thing and
the server did another).

AI7's cryptographic upgrade (`available as an upgrade... when the
deployment wants the witness-cosignature-grade guarantee`): pass
`crypto_verify_fn` to require the reviewer's identity be a verified,
signed attestation rather than a trusted metadata string — a reviewer
signing with the ACTOR's own key is refused exactly like a same-served-
model reviewer is, now enforced by signature instead of API metadata.
"""
from __future__ import annotations

from recurvelib.loop.reviewers import AdversaryVerdict
from recurvelib.adapters._shared.reviewer_base import run_isolated_review
from recurvelib.adapters._shared.provenance import Provenance, verified_different_identity
from recurvelib.adapters.adversary.same_model import _cmd, _parse, AdversaryReviewerError


class CrossModelIdentityViolation(AdversaryReviewerError):
    """The adversary pass's verified served identity does not verifiably
    differ from the actor's — refused, never silently treated as a clean
    pass. This is the exact bug class the O6 incident exposed: a same-model
    actor and prober agreeing on a wrong solution, unchallenged."""


class CrossModelAdversary:
    """`actor_provenance` is the (already-established) Provenance of
    whichever pass authored the claim/probe under review — required so this
    adapter has something to verify difference AGAINST, per R2's identity
    check. `crypto_verify_fn`, when supplied, upgrades the check from
    metadata to a real signature (AI7)."""

    def __init__(self, actor_provenance: Provenance, *, cmd: str | None = None,
                timeout: int = 300, crypto_verify_fn=None):
        self.actor_provenance = actor_provenance
        self.cmd = cmd
        self.timeout = timeout
        self.crypto_verify_fn = crypto_verify_fn
        self.last_provenance: Provenance | None = None

    def review(self, claim) -> AdversaryVerdict:
        inv = run_isolated_review(claim, _cmd(self.cmd), timeout=self.timeout)
        verdict, prov = _parse(inv, crypto_verify_fn=self.crypto_verify_fn)
        self.last_provenance = prov
        if not verified_different_identity(self.actor_provenance, prov):
            raise CrossModelIdentityViolation(
                f"adversary's verified served identity ({prov.identity!r}, "
                f"strength={prov.strength.value}) does not verifiably differ from the "
                f"actor's ({self.actor_provenance.identity!r}, "
                f"strength={self.actor_provenance.strength.value}) — cross_model refuses "
                f"rather than silently accepting a same-identity or unverified pair")
        return verdict
