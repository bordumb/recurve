"""KNOWN-BAD fixture: reintroduces a fourth hand-copy of the
build_X_registry/resolve_X pair instead of using the generic
build_registry/resolve -- exactly what the probe must reject."""
from __future__ import annotations


class UnknownAdapterError(ValueError):
    pass


class MalformedAdapterError(TypeError):
    pass


def build_proxy_registry(entries: dict[str, type]) -> dict[str, type]:
    return dict(entries)


def resolve_proxy(name: str, registry: dict[str, type]) -> type:
    if name not in registry:
        raise UnknownAdapterError(f"unknown proxy {name!r}")
    return registry[name]
