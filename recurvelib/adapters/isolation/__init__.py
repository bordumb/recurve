"""Isolation strategy: pluggable, selected PER ADAPTER — never per-run, never
globally (`docs/plans/ablation-infra.md` AI4). `subprocess_tempdir` is the
default; `docker` is available for an adapter that declares a heavy-runtime
requirement.
"""
from __future__ import annotations

STRATEGIES = ("subprocess_tempdir", "docker")


def resolve(name: str):
    """Return the isolation strategy module for `name`. Raises ValueError on
    an unknown strategy — the choice lives with the adapter's own declared
    needs, never silently defaulted."""
    if name == "subprocess_tempdir":
        from . import subprocess_tempdir
        return subprocess_tempdir
    if name == "docker":
        from . import docker
        return docker
    raise ValueError(f"unknown isolation strategy {name!r}; known: {', '.join(STRATEGIES)}")
