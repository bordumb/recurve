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

import re

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class OracleSpecError(ValueError):
    """The declared `[oracle.env]` is unpinnable or malformed — refused before a
    run, never graded against silently."""


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
