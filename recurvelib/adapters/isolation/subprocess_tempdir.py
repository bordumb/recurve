"""Default isolation strategy: a subprocess run with cwd pinned to a
snapshot root and a scrubbed environment (`docs/plans/ablation-infra.md` §4,
AI4).

Process isolation is already free the moment a reviewer is invoked as an
external process — a fresh process shares no Python memory and no
conversation with the acting agent's live session, with zero extra
engineering. This module is what makes the invocation's OWN hygiene
provable: the child is never handed a path or environment variable that
points outside the mounted snapshot.
"""
from __future__ import annotations

import dataclasses
import os
import subprocess

# Environment variable prefixes that MAY cross into an isolated invocation —
# everything else is scrubbed. Deliberately narrow: enough for the child to
# find its interpreter and reach its own model provider's API (network
# egress is the one thing this isolation does NOT restrict — the oracle runs
# --network=none; an adversary/governor adapter needs the opposite, §4's
# asymmetry). No credential or path from the acting agent's own session rides
# along by default.
ALLOWED_ENV_PREFIXES = ("PATH", "HOME", "LANG", "LC_", "ANTHROPIC_", "OPENAI_", "RECURVE_ISOLATED_")


@dataclasses.dataclass(frozen=True)
class IsolatedResult:
    returncode: int
    stdout: str
    stderr: str


def scrubbed_env(extra: dict | None = None) -> dict:
    """A minimal environment: only the allowed prefixes survive from the
    caller's own process environment, plus whatever `extra` explicitly adds."""
    env = {k: v for k, v in os.environ.items()
          if any(k.startswith(p) for p in ALLOWED_ENV_PREFIXES)}
    if extra:
        env.update(extra)
    return env


def run_isolated(snapshot_root, argv, *, timeout: int = 300,
                 extra_env: dict | None = None) -> IsolatedResult:
    """Run `argv` with cwd pinned to `snapshot_root` and a scrubbed
    environment. A fresh subprocess every call — no shared memory, no shared
    conversation, by construction."""
    proc = subprocess.run(
        list(argv), cwd=str(snapshot_root), env=scrubbed_env(extra_env),
        capture_output=True, text=True, timeout=timeout,
    )
    return IsolatedResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
