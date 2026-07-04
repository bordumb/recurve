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


def covered_by(exercises, surface_ids) -> set:
    """The surface ids covered by ANY of ``exercises`` — trace each one and union the surface points it runs.

    This is the aggregate that feeds the completeness gate with *measured* coverage: a surface point is covered
    iff some exercise (a claim's probe body) actually executes it. Deriving the covered set this way, instead
    of trusting each claim's declaration, is what makes coverage non-gameable end to end — a point every claim
    *says* it covers but none *runs* stays on the frontier.

    Args:
        exercises: Iterable of zero-argument callables — one per claim/probe.
        surface_ids: The surface point ids to attribute coverage to.

    Usage:
        covered = covered_by(probe_bodies, {p.id for p in surface})
        report = completeness_report(surface, covered)   # frontier = points no probe runs
    """
    surface_ids = set(surface_ids)
    covered: set = set()
    for exercise in exercises:
        try:
            covered |= measure_coverage(exercise, surface_ids)
        except (Exception, SystemExit):
            continue   # a probe body that raises OR calls sys.exit() (a RED/broken/skip-guarded probe)
            #            contributes no coverage — its points stay on the frontier — but never aborts the
            #            aggregate. A real KeyboardInterrupt still propagates and stops the run.
    return covered
