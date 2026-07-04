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

def cmd_freshness(args):
    from ... import render
    cfg = _config(args)
    ledger = _load(cfg)
    cache, seen, reports = {}, set(), []
    for g in ledger.gaps:
        if not g.needs_probe:
            continue
        key = (g.suite, g.reads)
        if key in seen:
            continue
        seen.add(key)
        reports.append(gap_freshness(cfg, g.suite, g.reads, cache))
    print(render.freshness_table(reports, cfg.label))
    if args.gate and any(r.blocks_gate for r in reports):
        raise SystemExit(1)
