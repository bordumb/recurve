"""CL-7 counterexample: only top-level functions are extracted; class methods are silently missed."""

import ast

from recurvelib.analysis.frontier import SurfacePoint


def extract(source, location=""):
    tree = ast.parse(source)
    pts = []
    for node in tree.body:  # BUG: never descends into ClassDef bodies -> methods are lost surface
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            loc = f"{location}:{node.lineno}" if location else str(node.lineno)
            pts.append(SurfacePoint(id=node.name, weight=0, kind="function", location=loc))
    pts.sort(key=lambda p: (p.id, p.location))
    return pts
