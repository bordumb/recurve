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

def cmd_cycle_new(args):
    from ... import render
    cfg = _config(args)
    ids = [s.strip() for s in args.gaps.split(",") if s.strip()]
    try:
        gaps = _load(cfg).select(ids)
    except GapParseError as e:
        _fail(str(e))
    matrix = run_matrix(gaps, cfg, timeout_s=args.timeout)
    baseline = re.sub(r"\033\[[0-9;]*m", "", render.matrix_table(matrix))
    plan = write_cycle_plan(cfg.cycles_dir, args.name, gaps, baseline,
                            prog=args.prog, label=cfg.label)
    print(f"wrote {plan}\nseed your cycle's work plan from it (spike-first when the fix needs design)")
