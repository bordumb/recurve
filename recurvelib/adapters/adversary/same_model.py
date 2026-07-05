"""same_model: isolated review, no cross-model identity requirement — still
worth doing: even the same model reviewing without its own prior reasoning
in context is a real, if weaker, check (R2, `docs/plans/ablation-infra.md`
§2/§4).

The reviewer is a BYO command (same shape as the acting agent's own
`CommandActor`): it runs in the isolated snapshot, reads the claim's
committed artifacts from its own cwd, and prints one JSON object on stdout:
`{"served_model": "<name>", "objection": null}` for a clean pass, or
`{"served_model": "<name>", "objection": {"fixture": "...", "rationale":
"..."}}` to propose a counterexample for the EXISTING `capture()` rule to
independently validate.

AI7's cryptographic upgrade: when the caller supplies `crypto_verify_fn`, a
reviewer MAY instead (or in addition) report `{"identity_public_key": "...",
"envelope": "..."}` — a signed attestation the adapter verifies via
`_shared.provenance.cryptographically_attested` instead of trusting the bare
`served_model` string. `metadata_verified` stays the default (cheap) tier
whenever `crypto_verify_fn` is absent, exactly as R2/AI7 specify.
"""
from __future__ import annotations

import json
import os

from recurvelib.loop.reviewers import AdversaryVerdict
from recurvelib.adapters._shared.reviewer_base import run_isolated_review
from recurvelib.adapters._shared.provenance import (
    Provenance, metadata_verified, unverified, cryptographically_attested,
)


class AdversaryReviewerError(Exception):
    """The configured reviewer command failed, or its output didn't follow
    the wire protocol — a controlled, typed failure, never a raw
    JSONDecodeError/CalledProcessError escaping the adapter."""


def _cmd(explicit: str | None) -> list[str]:
    cmd = explicit or os.environ.get("RECURVE_ADVERSARY_CMD")
    if not cmd:
        raise AdversaryReviewerError(
            "no adversary reviewer command configured (RECURVE_ADVERSARY_CMD, or cmd=) — "
            "same_model/cross_model never silently fall back to the main loop's AGENT_CMD")
    return cmd.split()


def _parse(inv, crypto_verify_fn=None) -> tuple[AdversaryVerdict, Provenance]:
    if inv.returncode != 0:
        raise AdversaryReviewerError(f"adversary reviewer exited {inv.returncode}: {inv.stderr[:200]}")
    try:
        payload = json.loads(inv.stdout.strip() or "{}")
    except json.JSONDecodeError as e:
        raise AdversaryReviewerError(f"adversary reviewer output was not valid JSON: {e}") from e
    if crypto_verify_fn is not None and payload.get("envelope") and payload.get("identity_public_key"):
        # AI7's upgrade path: verify a real signed attestation rather than
        # trusting a bare served_model string. A failed/forged envelope
        # demotes to unverified (cryptographically_attested's own contract)
        # — never silently accepted at the claimed strength.
        prov = cryptographically_attested(
            payload["identity_public_key"], payload["envelope"], crypto_verify_fn)
    else:
        served = payload.get("served_model")
        prov = metadata_verified(served) if served else unverified()
    obj = payload.get("objection")
    if not obj:
        return AdversaryVerdict.no_objection(), prov
    return AdversaryVerdict.proposed_trap(obj["fixture"], obj["rationale"]), prov


class SameModelAdversary:
    """Isolated review with no cross-model requirement. `review(claim)`
    takes an already-built `ClaimSnapshot` (the port's own shape) and runs
    the configured reviewer command against it via `run_isolated_review` —
    a fresh, isolated process every call."""

    def __init__(self, *, cmd: str | None = None, timeout: int = 300, crypto_verify_fn=None):
        self.cmd = cmd
        self.timeout = timeout
        self.crypto_verify_fn = crypto_verify_fn
        self.last_provenance: Provenance | None = None

    def review(self, claim) -> AdversaryVerdict:
        inv = run_isolated_review(claim, _cmd(self.cmd), timeout=self.timeout)
        verdict, prov = _parse(inv, crypto_verify_fn=self.crypto_verify_fn)
        self.last_provenance = prov
        return verdict
