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

def cmd_show(args):
    from recurvelib.io import render
    cfg = _config(args)
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        print(f"unknown gap id: {args.gap_id}", file=sys.stderr)
        raise SystemExit(2)
    print(render.gap_detail(g, cfg.label))
