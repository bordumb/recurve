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

def cmd_status(args):
    """One-glance health: open/closed claim counts, the TRUE gate verdict
    (computed from a full matrix run, never hardcoded), any broken/stale
    counts, and the pending draft backlog."""
    from recurvelib.io import render
    from recurvelib.io.status import summarize
    C = render.C
    cfg = _config(args)
    ledger = _load(cfg)
    matrix = run_matrix(list(ledger.gaps), cfg, timeout_s=args.timeout)
    s = summarize(ledger, matrix)
    drafts, _forks = _draft_backlog(cfg)
    pending = sum(d["pending"] for d in drafts)

    verdict = (f"{C['green']}PASS{C['reset']}" if s["gate_ok"]
               else f"{C['red']}FAIL{C['reset']}")
    print(f"{C['bold']}{cfg.name} — health{C['reset']}")
    print(f"  claims     {C['red']}{s['open']} open{C['reset']} · "
          f"{C['green']}{s['closed']} closed{C['reset']}")
    print(f"  gate       {verdict}")
    trouble = []
    if s["regressions"]:
        trouble.append(f"{s['regressions']} regression")
    if s["broken"]:
        trouble.append(f"{s['broken']} broken")
    if s["stale"]:
        trouble.append(f"{s['stale']} stale")
    if s["failed_traps"]:
        trouble.append(f"{s['failed_traps']} failed-trap")
    if trouble:
        print(f"  trouble    {C['amber']}{', '.join(trouble)}{C['reset']}")
    if pending:
        print(f"  drafts     {C['amber']}{pending} pending{C['reset']}")
    if args.gate and not s["gate_ok"]:
        raise SystemExit(1)
