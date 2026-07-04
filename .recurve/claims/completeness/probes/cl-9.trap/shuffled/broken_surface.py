"""CL-9 counterexample: the right points, in a randomized order — so two extractions disagree."""

import ast
import random

from recurvelib.analysis.frontier import SurfacePoint


def extract(source, location=""):
    tree = ast.parse(source)
    pts = []

    def add(name, lineno, prefix):
        if name.startswith("_"):
            return
        loc = f"{location}:{lineno}" if location else str(lineno)
        pts.append(SurfacePoint(id=f"{prefix}{name}", weight=0, kind="function", location=loc))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, node.lineno, "")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(item.name, item.lineno, f"{node.name}.")
    random.shuffle(pts)  # BUG: correct points, nondeterministic order -> not a stable baseline
    return pts
