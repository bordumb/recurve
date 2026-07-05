"""Opt-in isolation strategy for an adapter that declares a heavy, pinned
runtime requirement (`docs/plans/ablation-infra.md` §4, AI4).

An adversary/governor adapter is fundamentally "an LLM API call reviewing
text and code" — it needs a language client and network egress to reach its
provider, not a pinned scientific-computing runtime, so `subprocess_tempdir`
is the right default for `cross_model`/`mechanical_review`. This strategy
exists for a future adapter that genuinely needs one (a `kernel_verified`
governor requiring a Lean install, say) — selected per-adapter, never
imposed globally.
"""
from __future__ import annotations

import dataclasses
import shutil
import subprocess


class DockerUnavailable(Exception):
    """The docker strategy was selected but the docker CLI isn't usable."""


@dataclasses.dataclass(frozen=True)
class IsolatedResult:
    returncode: int
    stdout: str
    stderr: str


def available() -> bool:
    """True iff a `docker` binary is on PATH. Does not itself require the
    daemon to be reachable — callers that need that guarantee check via a
    real invocation, which fails closed with DockerUnavailable either way."""
    return shutil.which("docker") is not None


def run_isolated(snapshot_root, argv, image: str, *, timeout: int = 300,
                 network: str = "bridge") -> IsolatedResult:
    """Run `argv` inside `image`, with `snapshot_root` mounted READ-ONLY at
    `/snapshot` and cwd pinned there — the container's mount namespace is the
    isolation boundary, in place of the plain-subprocess cwd/env scrub."""
    if not available():
        raise DockerUnavailable("docker CLI not found on PATH")
    cmd = [
        "docker", "run", "--rm", "--network", network,
        "-v", f"{snapshot_root}:/snapshot:ro", "-w", "/snapshot",
        image, *argv,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise DockerUnavailable(f"docker could not be run: {e}") from e
    return IsolatedResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
