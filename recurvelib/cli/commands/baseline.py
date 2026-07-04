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

def cmd_baseline(args):
    import time
    from ... import render
    from ...baseline import run_baseline
    from ...lock import LockHeld
    C = render.C
    cfg = _config(args)
    adj = cfg.assets_dir / "ADJUDICATE.md"
    if adj.exists() and "DECIDED: (pending" in adj.read_text():
        pending = adj.read_text().count("DECIDED: (pending")
        print(f"\033[33m⚠ {pending} unresolved fork(s) in ADJUDICATE.md — claims touching "
              f"them will encode a guess, not a decision. One human sentence each.\033[0m")
    today = time.strftime("%Y-%m-%d")
    try:
        outcomes, ok = run_baseline(cfg, args.suite, today, timeout_s=args.timeout)
    except (GapParseError, ConfigError) as e:
        _fail(f"\033[31m✗ baseline failed:\033[0m {e}")
    except LockHeld as e:
        _fail(f"\033[31m✗ {e}\033[0m", 1)
    color = {"promoted-open": C["red"], "promoted-closed": C["green"],
             "kept-draft": C["amber"], "skipped": C["dim"]}
    for o in outcomes:
        print(f"  {color[o.action]}{o.action:<15}{C['reset']} {o.gap_id:<12} {render.dim(o.detail)}")
    if not ok:
        print(f"{C['red']}✗ baseline incomplete — fix the harness/traps above; "
              f"do not start a cycle on a broken baseline.{C['reset']}")
        raise SystemExit(1)
    print(f"{C['green']}✓ baseline complete{C['reset']} — promoted entries are now "
          f"measurements; the ledger stays a record of observations.")
