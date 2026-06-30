"""Measured coverage: which surface points a probe *actually exercises*, not what it claims to.

Declared coverage (a claim's ``covers`` field) is convenient but gameable — a claim can assert it covers a
point it never touches. Measured coverage closes that gap: run the exercise under tracing and record the
functions it really calls, intersected with the known surface. This is the strong source that slots into
:func:`recurvelib.completeness.completeness_report` in place of declarations — a point counts as covered only
when a probe is observed to run it.
"""
from __future__ import annotations

import sys


def measure_coverage(exercise, surface_ids=None) -> set:
    """Run ``exercise()`` under tracing and return the (qualified) function names it called.

    Args:
        exercise: A zero-argument callable that drives the behavior under test.
        surface_ids: Optional set of surface ids; when given, the result is intersected with it so only
            known surface points are reported (no stdlib/phantom names).

    Returns:
        The set of qualified function names observed called during ``exercise`` (∩ ``surface_ids`` if given).

    Usage:
        covered = measure_coverage(lambda: client.open(), surface_ids={"Client.open", "Client.close"})
        # feed `covered` into completeness_report(surface, covered) for a non-gameable frontier.
    """
    called: set = set()

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

    if surface_ids is not None:
        return called & set(surface_ids)
    return called
