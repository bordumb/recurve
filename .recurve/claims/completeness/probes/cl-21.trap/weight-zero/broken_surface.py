"""CL-21 counterexample: every point gets weight 0, so the frontier ranking collapses to alphabetical and
the most consequential uncovered unit is not claimed first."""

import ast

from recurvelib.analysis.frontier import SurfacePoint


def extract(source, location=""):
    tree = ast.parse(source)
    points = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            loc = f"{location}:{node.lineno}" if location else str(node.lineno)
            points.append(SurfacePoint(id=node.name, weight=0, kind="function", location=loc))  # BUG: weight 0
    points.sort(key=lambda p: (p.id, p.location))
    return points
