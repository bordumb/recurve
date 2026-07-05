"""oracle_build.py — the oracle image is derivable-from-repo, reconciled to the pin.

A docker rebuild is not bit-reproducible (build-time downloads), so a silently
rebuilt image would quietly become the oracle and bypass the pin → lock →
calibration chain. This module makes the rebuild an EXPLICIT verb and reconciles
its result against the manifest pin: match → proceed; mismatch → refuse, naming
the remediation (update the pin, rebuild the lock, recalibrate — a different image
is a different oracle, its calibration stale by definition). The reconcile +
remediation logic is pure; only the build itself touches docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# The one command a fresh clone runs to derive the oracle image from the repo.
BUILD_VERB = "eval oracle build"


class OracleImageMismatch(RuntimeError):
    """A rebuilt image's digest diverges from the manifest pin — refused rather
    than silently adopted (a different image is a different oracle)."""


def missing_image_remediation(image: str, digest: str) -> str:
    """The message `plan` prints when the pinned image is absent locally — it
    names the one-command remediation so a fresh clone reaches ready-to-plan."""
    return (f"oracle image {image} @ {digest} is not present locally — derive it "
            f"from the committed Dockerfile with `{BUILD_VERB}` (build-time network "
            f"only; grading stays --network=none), then re-run `eval plan`.")


def reconcile_digest(built: str, pinned: str) -> str:
    """`match` if a freshly-built image equals the manifest pin; otherwise raise
    OracleImageMismatch with a remediation that names the re-pin + recalibrate
    steps. Never silently adopts a divergent rebuild."""
    if built == pinned:
        return "match"
    raise OracleImageMismatch(
        f"built image {built} != manifest pin {pinned} — a different image is a "
        f"different oracle. Update [oracle.env].digest to {built}, re-run `eval plan` "
        f"to rebuild oracle.lock.json, and RECALIBRATE (the old calibration is stale "
        f"by definition). Refusing to silently adopt a rebuilt image.")


def build_image(dockerfile: str | Path, tag: str,
                context: str | Path) -> str:  # pragma: no cover - needs docker+network
    """Build the derived oracle image from the committed Dockerfile and return its
    content Id. Build-time network is allowed (the base is digest-pinned, so the
    pull is deterministic); grade-time stays --network=none."""
    # --provenance/--sbom off: buildx attestations stamp timestamps into the
    # image manifest, making the Id non-deterministic; disabling them makes a
    # rebuild reproduce the same Id, so the committed pin matches a fresh build.
    subprocess.run(
        ["docker", "build", "--provenance=false", "--sbom=false",
         "--platform", "linux/amd64", "-t", tag,
         "-f", str(dockerfile), str(context)], check=True)
    r = subprocess.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()
