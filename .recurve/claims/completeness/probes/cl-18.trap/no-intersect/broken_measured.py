"""CL-18 counterexample: a measurer that returns every called name without intersecting the surface — so
off-surface calls (helpers, stdlib) leak in as phantom coverage and pollute the accounting."""

import sys


def measure_coverage(exercise, surface_ids=None):
    called = set()

    def tracer(frame, event, arg):
        if event == "call":
            code = frame.f_code
            called.add(getattr(code, "co_qualname", code.co_name))
        return tracer

    prev = sys.gettrace()
    sys.settrace(tracer)
    try:
        exercise()
    finally:
        sys.settrace(prev)
    return called  # BUG: never intersects with surface_ids
