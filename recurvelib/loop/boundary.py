"""Boundary: the pluggable write-boundary port.

`within_boundary()` in `recurvelib.loop.runtime` is the pure predicate that
decides whether a diff's paths stay inside the target tree and off the
referee surface. This module adds a PORT around it — the same shape as
`Adversary`/`Governor` in `recurvelib.loop.reviewers`: a `Protocol` plus
concrete adapters resolved through `recurvelib.adapters.registry`.
`within_boundary` and `runtime.py` itself are untouched by this module —
nothing here imports or mutates them, and (like Adversary/Governor before it)
the only production consumer that changes is `recurvelib.loop.adapters.GitWorld`
(a new, DEFAULTED `boundary=` constructor argument), never the pure predicate.

This is the one port this package treats as inherently dangerous: `open`
disables the check that keeps an autonomous actor off the referee surface
(claims/probes/traps) — the exact thing `within_boundary` exists to prevent.
It is off by default (`enforced`), reachable only through the literal
`[gate] boundary = "open"` key (`recurvelib.core.config`) — no other config
path produces this value by coincidence — and it is LOUD: `OpenBoundary`
prints an unmissable warning on every single check, never silently.
"""
from __future__ import annotations

import sys
from typing import Protocol

from recurvelib.loop.runtime import within_boundary


class Boundary(Protocol):
    """A pluggable write-boundary check. Given the diff's paths, the target
    root, and the referee roots it must never touch, decide whether the
    patch may be applied at all."""

    def check(self, diff_paths, target_root: str, referee_roots) -> bool: ...


class EnforcedBoundary:
    """BoundaryPort["enforced"] — the default, and the only behavior that
    existed before this port did. Delegates to the SAME `within_boundary`
    predicate every other caller uses; adding this port changes nothing
    about how the check itself works."""

    def check(self, diff_paths, target_root: str, referee_roots) -> bool:
        return within_boundary(diff_paths, target_root, referee_roots)


class OpenBoundary:
    """BoundaryPort["open"] — the dangerous bypass. Always permits the
    write, unconditionally, and LOUDLY: every single call prints a fixed,
    grep-able warning to stderr, so this can never be exercised silently."""

    WARNING = ("BOUNDARY OPEN: write-boundary check BYPASSED — the referee "
               "surface (claims/probes/traps) is UNPROTECTED for this apply.")

    def check(self, diff_paths, target_root: str, referee_roots) -> bool:
        print(self.WARNING, file=sys.stderr)
        return True
