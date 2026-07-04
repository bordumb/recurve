"""BROKEN counterexample for SR-3: a materialize that returns the shipped
template un-interpolated. Its `${RECURVE_BIN:-{{PROG}}}` mis-parses under bash
(the `}}` leaks into PROG), so the loop cannot run — the placeholders must be
interpolated first."""


def materialize_workflow(cfg, script):
    return script
