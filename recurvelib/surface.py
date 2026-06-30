"""Surface extraction: the set of claimable points in a target.

A *surface point* is a unit that could be claimed. Extraction is **adapter-based** — the generic core knows
only the abstract :class:`~recurvelib.frontier.SurfacePoint`; an adapter knows how to read points from a
given target (a language, a runtime). Extraction is **deterministic and LLM-free**: the same target yields
the same surface, diffable and versionable, so coverage regressions are detectable. The points produced here
are exactly what :func:`recurvelib.frontier.compute_frontier` consumes — together they answer "what is the
surface, and what of it does no claim cover?"
"""
from __future__ import annotations

import ast
from typing import Protocol

from recurvelib.frontier import SurfacePoint


class Adapter(Protocol):
    """A surface adapter: reads claimable points out of a target's source for one language/runtime.

    Args:
        source: The target source text.
        location: Optional path, prefixed onto each point's location for reporting.
    """

    def extract(self, source: str, location: str = "") -> list[SurfacePoint]: ...


class PythonAdapter:
    """Extract one surface point per public function/method from Python source (via the ``ast``).

    A point's id is its qualified name (``func`` for a module-level function, ``Class.method`` for a method).
    Names with a leading underscore — and the methods of underscore-prefixed classes — are implementation,
    not claimable surface, and are excluded. Output is sorted by ``(id, location)`` for determinism.

    Usage:
        points = PythonAdapter().extract(source_text, location="pkg/mod.py")
    """

    def extract(self, source: str, location: str = "") -> list[SurfacePoint]:
        tree = ast.parse(source)
        points: list[SurfacePoint] = []

        def add(name: str, lineno: int, prefix: str) -> None:
            if name.startswith("_"):
                return
            loc = f"{location}:{lineno}" if location else str(lineno)
            points.append(SurfacePoint(id=f"{prefix}{name}", weight=0, kind="function", location=loc))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node.name, node.lineno, "")
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        add(item.name, item.lineno, f"{node.name}.")

        points.sort(key=lambda p: (p.id, p.location))
        return points


def extract_surface(source: str, adapter: Adapter, location: str = "") -> list[SurfacePoint]:
    """Extract the claimable surface points from a target's source using ``adapter``.

    Args:
        source: The target source text.
        adapter: A surface adapter for the target's language/runtime.
        location: Optional path prefixed onto each point's location.

    Usage:
        surface = extract_surface(src, PythonAdapter(), location="pkg/mod.py")
        # feed `surface` straight into compute_frontier(surface, covered_ids, deferred_ids)
    """
    return adapter.extract(source, location)
