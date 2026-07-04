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

def cmd_probe(args):
    from recurvelib.io import render
    cfg = _config(args)
    gaps = _filter(_load(cfg), args.suite, args.gap)
    matrix = run_matrix(gaps, cfg, timeout_s=args.timeout)
    print(render.matrix_table(matrix))
