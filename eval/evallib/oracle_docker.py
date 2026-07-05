"""oracle_docker.py — the docker-specific probes that resolve an oracle lock.

The pure spec/lock/hash logic lives in oracle_env.py; this is the impure half
that actually queries docker and the host. It is exercised only on the plan path
of a real run (a docker manifest), never in the hermetic gate — the resolution
logic is tested there with injected probes.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path

from evallib.oracle_env import parse_oracle_env, resolve_oracle_lock


def wrapper_path() -> Path:
    """The committed docker grading wrapper (RECURVE_ORACLE_PYTHON points here)."""
    return Path(__file__).resolve().parents[1] / "oracle" / "oracle_docker.sh"


def wrapper_sha(path: str | Path | None = None) -> str:
    p = Path(path) if path else wrapper_path()
    return "wsha:" + hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def host_fingerprint() -> str:
    """A stable-ish host identity. Included in the oracle-env hash because under
    emulation the machine changes timing, and timing changes timeout verdicts —
    so a new host must re-calibrate."""
    return f"{platform.system()}/{platform.machine()}/{platform.release()}"


def local_image_digest(image: str, digest: str):  # pragma: no cover - needs docker
    """`digest` if the pinned image is present locally, else None (drift/absent →
    refused). Resolves a locally-built image by its content Id (`sha256:…`) and a
    pulled image by its `image@repodigest`; the pin is one immutable digest either
    way."""
    for ref in (digest, f"{image}@{digest}"):
        if subprocess.run(["docker", "image", "inspect", ref],
                          capture_output=True).returncode == 0:
            return digest
    return None


def container_python(image: str, digest: str) -> str:  # pragma: no cover - needs docker
    """The grading interpreter's version string, read from inside the pinned
    image (referenced by its content-addressed digest)."""
    r = subprocess.run(
        ["docker", "run", "--rm", "--platform", "linux/amd64", "--entrypoint",
         "python", digest, "--version"],
        capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def build_lock(manifest: dict) -> dict:  # pragma: no cover - needs docker for a docker manifest
    """Resolve `[oracle.env]` against this machine into a lock. For a docker
    oracle this queries docker (digest present, container python); for a local
    oracle it records the current interpreter. Raises OracleDriftError if the
    pinned image is not present locally."""
    spec = parse_oracle_env(manifest)
    ws = wrapper_sha()
    host = host_fingerprint()
    if spec["mode"] == "docker":
        return resolve_oracle_lock(
            spec, digest_probe=lambda image: local_image_digest(image, spec["digest"]),
            python_probe=lambda image, digest: container_python(image, digest),
            wrapper_sha=ws, host=host)
    return resolve_oracle_lock(
        spec, python_probe=lambda: platform.python_version(), wrapper_sha=ws, host=host)
