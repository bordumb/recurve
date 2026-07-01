"""BROKEN counterexample for TK-21: a run_demo whose trace never shows a
failing probe. It reports GREEN from the start and skips the RED step, so it
claims to demonstrate a fix without ever having a broken check to fix. A demo
that greenwashes like this teaches nothing — there is no transition to watch.
The TK-21 probe must turn RED against it."""

from pathlib import Path


def run_demo(workdir):
    workdir = Path(workdir)
    # The defect: the trace has only a GREEN step. There is no RED before it,
    # so nothing was ever demonstrated to go from failing to passing.
    steps = [{"phase": "after", "probe": "GREEN"}]
    return {"steps": steps, "gate_ok": True, "workdir": str(workdir)}
