"""CL-8 counterexample: underscore-prefixed functions/methods are extracted as surface (they are not)."""

import ast

from recurvelib.frontier import SurfacePoint


def extract(source, location=""):
    tree = ast.parse(source)
    pts = []

    def add(name, lineno, prefix):
        loc = f"{location}:{lineno}" if location else str(lineno)
        pts.append(SurfacePoint(id=f"{prefix}{name}", weight=0, kind="function", location=loc))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, node.lineno, "")  # BUG: no leading-underscore exclusion
        elif isinstance(node, ast.ClassDef):  # BUG: also descends into private classes
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(item.name, item.lineno, f"{node.name}.")
    pts.sort(key=lambda p: (p.id, p.location))
    return pts
