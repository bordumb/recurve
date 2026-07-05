"""oracle_env.py — the oracle environment as a first-class, pinned citizen.

The oracle is the other half of the experiment. Which interpreter/image graded a
solution can change its verdict, and under emulation even its *timing* can change
a verdict (a fixed timeout turns a slow pass into an error). So the oracle env is
naturalized under the same rule the dataset already lives by:

    anything that can change a verdict must be pinned and refused-on-drift;
    anything that can change a timing must be recorded;
    the manifest is human intent, the lock is machine-resolved truth.

This module is the INTENT half: parse and validate `[oracle.env]`. A docker
oracle MUST carry an immutable `sha256:` digest — a bare `:tag` is mutable, so
retagging it would let two runs grade against different images under the same
name with nothing to show it. The RESOLUTION half (querying the digest actually
present, writing `oracle.lock.json`, refusing drift) lives in the plan path.
"""

from __future__ import annotations

import hashlib
import json
import re

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# The VERDICT-AFFECTING identity of an oracle. `oracle_env_hash` digests exactly
# these — deliberately NOT the calibration-derived timeout/exclusions, which are
# keyed BY this hash (including them would be circular). `host` is here because
# under emulation a different machine changes timing, and timing changes timeout
# verdicts, so a new host must re-calibrate.
_IDENTITY_KEYS = ("mode", "image", "digest", "platform", "network",
                  "container_python", "wrapper_sha", "host")


class OracleSpecError(ValueError):
    """The declared `[oracle.env]` is unpinnable or malformed — refused before a
    run, never graded against silently."""


class OracleDriftError(RuntimeError):
    """The oracle image actually present locally does not match the manifest's
    pinned digest — refused, exactly as a dataset hash mismatch is."""


def parse_oracle_env(manifest: dict) -> dict:
    """Validate `[oracle.env]` and return a normalized spec. Raises
    OracleSpecError on any spec that could not be pinned to an immutable oracle.

    docker → requires `image` (a bare repository name) + `digest`
    ('sha256:<64hex>'); a tag or digest smuggled into `image` is refused so the
    digest field is the single source of truth. local → the hermetic fallback
    (the current interpreter); no image/digest, used for dev and hermetic tests.
    """
    env = (manifest or {}).get("oracle", {}).get("env")
    if not env:
        raise OracleSpecError(
            "manifest has no [oracle.env] — the oracle that grades every solution "
            "must be declared, exactly as the dataset is")
    mode = env.get("mode")
    if mode == "docker":
        image = env.get("image", "")
        digest = env.get("digest", "")
        last = image.rsplit("/", 1)[-1]
        if "@" in image or ":" in last:
            raise OracleSpecError(
                f"oracle image {image!r} must be a bare repository name — the "
                f"digest is pinned separately in `digest`, not in the image")
        if not image:
            raise OracleSpecError("docker oracle requires an `image`")
        if not DIGEST_RE.match(digest):
            raise OracleSpecError(
                f"docker oracle requires an immutable digest 'sha256:<64hex>', "
                f"got {digest!r} — a bare tag is mutable and cannot pin an oracle")
        return {
            "mode": "docker", "image": image, "digest": digest,
            "platform": env.get("platform", "linux/amd64"),
            "network": env.get("network", "none"),
            "timeout": env.get("timeout", "calibrated"),
        }
    if mode == "local":
        return {"mode": "local", "timeout": env.get("timeout", "calibrated")}
    raise OracleSpecError(
        f"unknown oracle mode {mode!r}; expected 'docker' (pinned image) or "
        f"'local' (the current interpreter, for hermetic tests)")


def oracle_env_hash(lock: dict) -> str:
    """Digest the verdict-affecting identity of a lock — stable across the
    calibration-derived fields it keys, so calibration can hang off it without a
    circular dependency."""
    canon = json.dumps({k: lock.get(k) for k in _IDENTITY_KEYS},
                       sort_keys=True, separators=(",", ":"))
    return "oeh:" + hashlib.sha256(canon.encode()).hexdigest()[:32]


def resolve_oracle_lock(spec: dict, *, digest_probe=None, python_probe=None,
                        wrapper_sha: str = "", host: str = "",
                        grade_concurrency: int = 1) -> dict:
    """Resolve a validated spec against the machine into an oracle lock.

    `digest_probe(image)` returns the image digest actually present locally (None
    if absent); a docker oracle whose local digest disagrees with the manifest —
    or is absent — raises OracleDriftError, the same refusal the dataset hash
    gives. `python_probe(...)` returns the grading interpreter's version string.
    The lock carries the identity fields plus empty slots for the timeout and
    exclusion hash that calibration fills in; `oracle_env_hash` covers the
    identity only."""
    mode = spec["mode"]
    if mode == "docker":
        present = digest_probe(spec["image"]) if digest_probe else None
        if present != spec["digest"]:
            raise OracleDriftError(
                f"oracle image {spec['image']} present locally as {present!r}, "
                f"manifest pins {spec['digest']!r} — refusing to grade against a "
                f"different (or absent) image")
        container_python = python_probe(spec["image"], spec["digest"]) if python_probe else ""
        lock = {"mode": "docker", "image": spec["image"], "digest": spec["digest"],
                "platform": spec["platform"], "network": spec["network"],
                "container_python": container_python, "wrapper_sha": wrapper_sha,
                "host": host}
    else:
        container_python = python_probe() if python_probe else ""
        lock = {"mode": "local", "image": "", "digest": "", "platform": "",
                "network": "none", "container_python": container_python,
                "wrapper_sha": wrapper_sha, "host": host}
    lock["timeout_policy"] = spec.get("timeout", "calibrated")
    lock["resolved_timeout"] = None   # filled by the calibration run
    lock["exclusion_hash"] = None     # filled by the calibration run
    # Recorded, checked against the run's actual concurrency (O4), but NOT part of
    # the identity — the serial-retry protection means concurrency changes timing,
    # not verdicts, so it must not invalidate a calibration.
    lock["grade_concurrency"] = int(grade_concurrency)
    lock["oracle_env_hash"] = oracle_env_hash(lock)
    return lock
