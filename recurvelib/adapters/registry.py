"""The adapter registry — a plain dict, not a plugin-discovery system
(`docs/plans/ablation-infra.md` §3, AI2).

`[gate] adversary = "cross_model"` / `[gate] governor = "mechanical_review"`
resolve through these registries. The load-bearing property:
`recurvelib.loop.runtime` depends only on the `Adversary`/`Governor`
protocols, never on a concrete adapter class — adding adapter N+1 is a new
file plus one registry line, with zero changes to the loop, the controller,
or `decide()`.
"""
from __future__ import annotations

from recurvelib.loop.reviewers import Adversary, Governor
from recurvelib.loop.boundary import Boundary


class UnknownAdapterError(ValueError):
    """A config named an adapter no registry entry matches."""


class MalformedAdapterError(TypeError):
    """A registered adapter class doesn't implement the full protocol — this
    is refused at REGISTRATION time, never discovered at first invocation
    mid-run (AI2's counterexample)."""


def _require_methods(cls: type, protocol: type, methods: tuple[str, ...]) -> None:
    missing = [m for m in methods if not hasattr(cls, m)]
    if missing:
        raise MalformedAdapterError(
            f"{cls!r} does not implement {protocol.__name__}.{'/'.join(missing)} — "
            f"refused at registration, not at first invocation")


def build_adversary_registry(entries: dict[str, type]) -> dict[str, type]:
    """Validate and return an adversary registry: every entry must implement
    `Adversary.review`. Raises `MalformedAdapterError` immediately on a bad
    entry — registration fails loud, not silently at call time."""
    for name, cls in entries.items():
        _require_methods(cls, Adversary, ("review",))
    return dict(entries)


def build_governor_registry(entries: dict[str, type]) -> dict[str, type]:
    """Validate and return a governor registry: every entry must implement
    `Governor.audit`."""
    for name, cls in entries.items():
        _require_methods(cls, Governor, ("audit",))
    return dict(entries)


def resolve_adversary(name: str, registry: dict[str, type]) -> type:
    if name not in registry:
        raise UnknownAdapterError(f"unknown adversary {name!r}; known: {', '.join(sorted(registry))}")
    return registry[name]


def resolve_governor(name: str, registry: dict[str, type]) -> type:
    if name not in registry:
        raise UnknownAdapterError(f"unknown governor {name!r}; known: {', '.join(sorted(registry))}")
    return registry[name]


def build_boundary_registry(entries: dict[str, type]) -> dict[str, type]:
    """Validate and return a boundary registry: every entry must implement
    `Boundary.check`. Raises `MalformedAdapterError` immediately on a bad
    entry — registration fails loud, not at first apply()."""
    for name, cls in entries.items():
        _require_methods(cls, Boundary, ("check",))
    return dict(entries)


def resolve_boundary(name: str, registry: dict[str, type]) -> type:
    if name not in registry:
        raise UnknownAdapterError(f"unknown boundary {name!r}; known: {', '.join(sorted(registry))}")
    return registry[name]
