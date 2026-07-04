"""CL-20 counterexample: lets ast.parse raise, so one unparseable target aborts the whole completeness pass."""

import ast


def extract(source, location=""):
    ast.parse(source)  # BUG: uncaught SyntaxError on an unparseable target
    return []
