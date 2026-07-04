from __future__ import annotations

from ..base import *  # shared recurvelib imports
from ..base import (
    _fail,
    _config,
    _load,
    _filter,
    _parse_point,
    _parse_goal,
    _draft_backlog,
)

def cmd_demo(args):
    """Zero-setup sign-of-life. Runs one claim from RED to GREEN inside a fresh
    temp dir — no config, no network, no agent, no cwd pollution — and prints a
    compact narrative of the loop's shape (claim → probe → gate → green). The
    temp dir is removed before returning."""
    import tempfile
    from ... import render
    from ...demo import run_demo
    C = render.C
    with tempfile.TemporaryDirectory(prefix="recurve-demo-") as tmp:
        trace = run_demo(Path(tmp))
    steps = trace["steps"]
    before = next((s for s in steps if s["probe"] == "RED"), None)
    after = next((s for s in steps if s["probe"] == "GREEN"), None)

    def mark(probe: str) -> str:
        return (f"{C['red']}RED{C['reset']}" if probe == "RED"
                else f"{C['green']}GREEN{C['reset']}")

    print(f"{C['bold']}recurve demo{C['reset']} — one claim, RED → GREEN, behind the gate")
    print(render.dim("  (ran in a throwaway temp dir; nothing written to your cwd)"))
    print(f"  claim   the target says 'ready'")
    print(f"  probe   reads the tree and returns RED or GREEN")
    if before:
        print(f"  {mark(before['probe'])}     probe fails — the claim is unmet")
    print(render.dim("  fix     write 'ready' to the target (the trivial change)"))
    if after:
        print(f"  {mark(after['probe'])}   same probe passes — the claim now holds")
    verdict = (f"{C['green']}open{C['reset']}" if trace["gate_ok"]
               else f"{C['red']}shut{C['reset']}")
    print(f"  gate    {verdict} — a claim promotes only when its probe is GREEN")
    if before and after:
        print(f"\n{C['green']}✓ watched a failing probe go green.{C['reset']} "
              f"That RED → GREEN transition, gated, is the whole loop.")
    else:
        print(f"\n{C['red']}✗ demo did not show a real RED → GREEN transition.{C['reset']}")
        raise SystemExit(1)
