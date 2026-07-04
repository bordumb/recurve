"""CL-19 counterexample: walks only direct body children, so a def nested under if/for/try (e.g. a
TYPE_CHECKING-guarded or import-fallback method) is silently dropped from the surface."""

import ast

from recurvelib.frontier import SurfacePoint


def extract(source, location=""):
    tree = ast.parse(source)
    points = []

    def add(name, lineno, prefix):
        if name.startswith("_"):
            return
        loc = f"{location}:{lineno}" if location else str(lineno)
        points.append(SurfacePoint(id=f"{prefix}{name}", weight=0, kind="function", location=loc))

    for node in tree.body:  # BUG: never descends through if/for/try wrappers
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, node.lineno, "")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(item.name, item.lineno, f"{node.name}.")
    points.sort(key=lambda p: (p.id, p.location))
    return points
