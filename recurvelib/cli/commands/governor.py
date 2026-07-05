from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from ..base import *  # shared recurvelib imports
from ..base import _fail, _config


def _shell_verify_fn(verifier_cmd: str):
    """Wrap a configured shell command into the `verify_fn(payload_bytes,
    signature, public_key) -> bool` shape `human_required` needs — the same
    seam `[receipts] verifier` already uses: the command receives the
    payload bytes on stdin and the signature + public key as argv, and
    exits 0 iff the signature verifies."""

    def verify(payload_bytes: bytes, signature: str, public_key: str) -> bool:
        try:
            r = subprocess.run(shlex.split(verifier_cmd) + [signature, public_key],
                              input=payload_bytes, capture_output=True, timeout=60)
        except Exception:
            return False
        return r.returncode == 0

    return verify


def cmd_governor(args):
    """`recurve governor approve <claim_id...> --attestation <path>`: read an
    already-signed attestation (produced by a human's own tooling — e.g.
    `auths sign` run interactively, Touch-ID-gated), verify it against the
    configured `[gate] human_verifier` command, and — only if it verifies —
    register it where `HumanRequiredGovernor` looks for it. An attestation
    that fails to verify is refused outright; nothing is registered."""
    from recurvelib.adapters.governor.human_required import (
        cycle_snapshot_hash, verify_attestation, AttestationError,
    )

    cfg = _config(args)
    if args.action != "approve":
        _fail(f"unknown governor action: {args.action}")

    att_path = Path(args.attestation)
    if not att_path.is_file():
        _fail(f"no attestation file at {att_path}")
    try:
        att = json.loads(att_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        _fail(f"attestation at {att_path} is not valid JSON: {e}")

    verifier_cmd = getattr(cfg, "human_verifier", "") or ""
    if not verifier_cmd:
        _fail("no [gate] human_verifier configured — an attestation cannot be verified "
              "without one; human_required never accepts an attestation on faith")

    class _Cycle:
        def __init__(self, commit, claim_ids):
            self.commit = commit
            self.claim_ids = claim_ids

    claim_ids = args.claim_ids or att.get("payload", {}).get("claim_ids", [])
    ref_commit = att.get("payload", {}).get("_verify_commit") or args.ref
    if not ref_commit:
        _fail("no commit to verify the attestation's cycle_snapshot_hash against — pass --ref")
    cycle = _Cycle(ref_commit, claim_ids)

    ok, reason = verify_attestation(att, cycle, _shell_verify_fn(verifier_cmd))
    if not ok:
        _fail(f"attestation refused: {reason}")

    out_dir = cfg.state_dir / "attestations"
    out_dir.mkdir(parents=True, exist_ok=True)
    h = cycle_snapshot_hash(cycle)
    (out_dir / f"{h}.json").write_text(json.dumps(att, sort_keys=True, indent=2))
    print(f"attestation verified and registered for cycle {h[:12]} — "
          f"decision={att['payload'].get('decision')}")
