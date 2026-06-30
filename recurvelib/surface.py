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

# Statement wrappers a def can hide inside at module or class scope: a method under `if TYPE_CHECKING:`,
# a function under `try/except ImportError:`, a platform `if`, a `for`/`with`. They are still surface.
_WRAPPERS = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)


def _defs_in(body):
    """Yield the function/class defs in ``body``, descending THROUGH conditional wrappers but NOT into a
    def's own body (a nested function is implementation, not surface)."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node
        elif isinstance(node, _WRAPPERS):
            yield from _defs_in(list(ast.iter_child_nodes(node)))


def _weight(node) -> int:
    """A complexity proxy: the number of AST nodes in the def. Bigger/branchier units rank higher on the
    frontier, so the most consequential uncovered point is claimed first (not just the alphabetical one)."""
    return sum(1 for _ in ast.walk(node))


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
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []  # an unparseable target has a defined, empty surface — it never crashes the pass
        points: list[SurfacePoint] = []

        def add(node, prefix: str) -> None:
            if node.name.startswith("_"):
                return
            loc = f"{location}:{node.lineno}" if location else str(node.lineno)
            points.append(
                SurfacePoint(id=f"{prefix}{node.name}", weight=_weight(node), kind="function", location=loc)
            )

        for node in _defs_in(tree.body):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node, "")
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for item in _defs_in(node.body):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        add(item, f"{node.name}.")

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
