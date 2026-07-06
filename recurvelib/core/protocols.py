"""Pluggable, untrusted ports outside the confirmation loop's own spine
(`recurvelib.loop.runtime`'s `Actor`/`World`). `ProxyEvaluator` guides a
search; it never decides one — the gate (`matrix --gate`) is the only
arbiter a candidate's status can come from.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProxyScore:
    """`value` in [0, 1] (higher = more promising) ranks candidates; it never
    promotes, closes, or otherwise earns one a ledger entry. `signal` is a
    structured extra (e.g. a violation magnitude) for a breeding step to use,
    not for ranking."""

    value: float
    signal: Any = None


class ProxyEvaluator(Protocol):
    """A cheap, untrusted scorer. MUST be pure/deterministic given a candidate
    and a fixed sample seed, and MUST NOT write to the tree or invoke the
    gate — a proxy that could do either would blur the one line this whole
    design depends on: the proxy ranks, the gate decides."""

    def score(self, candidate: Any) -> ProxyScore: ...
