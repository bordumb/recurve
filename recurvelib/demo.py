"""A zero-setup sign-of-life: watch one claim go RED then GREEN behind a gate.

`run_demo` is a pure function. Given a working directory, it builds a tiny
claim and a probe that checks it, runs the probe once while the claim is unmet
(RED), applies a trivial fix so the same probe passes (GREEN), and confirms the
gate would let the fixed claim through. It returns a structured trace of that
RED -> GREEN transition. It writes only inside the working directory it is
given and reads nothing outside it, so a caller can hand it a throwaway temp
dir and be sure the demo leaves nothing behind.

The point: the fastest way to understand recurve is to watch one claim go from
RED to GREEN once the check is satisfied.
"""

from __future__ import annotations

from pathlib import Path


def _probe_verdict(target: Path) -> str:
    """The demo's mini-probe: the claim is 'the target file says ready'. The
    probe reports GREEN when the file exists and contains the word 'ready',
    RED otherwise. This is the whole loop in miniature: a claim, a check that
    reads the tree, and a RED/GREEN verdict."""
    if target.exists() and "ready" in target.read_text():
        return "GREEN"
    return "RED"


def run_demo(workdir: Path) -> dict:
    """Run one RED -> GREEN cycle inside `workdir` and return its trace.

    The trace is a dict with:
      steps    — ordered list of {"phase", "probe"} observations; the first is
                 the claim unmet (RED), the last is the same probe after a
                 trivial fix (GREEN)
      gate_ok  — True when the final probe is GREEN (what a gate would need to
                 promote the claim)
      workdir  — the directory the demo ran in (as a string)

    All work happens under `workdir`; nothing outside it is written or read.
    """
    workdir = Path(workdir)
    target = workdir / "claim-target.txt"

    steps: list[dict] = []

    # Before the fix: the claim's target does not yet say 'ready', so the probe
    # is RED. This is a real failing check, not a label.
    steps.append({"phase": "before", "probe": _probe_verdict(target)})

    # The trivial fix: make the tree satisfy the claim.
    target.write_text("ready\n")

    # After the fix: the same probe, re-run against the changed tree, is GREEN.
    steps.append({"phase": "after", "probe": _probe_verdict(target)})

    gate_ok = steps[-1]["probe"] == "GREEN"
    return {"steps": steps, "gate_ok": gate_ok, "workdir": str(workdir)}
