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

def cmd_decide(args):
    from recurvelib.analysis.decide_cli import verdict_for

    # A config, when one resolves, brings [gate] governor= into the decision
    # for real (R5's live wiring) — the exact call
    # templates/workflows/burndown.sh's stop_verdict() already makes.
    # `recurve decide` has no hard project-context requirement: called with
    # no recurve.toml anywhere upward, cfg stays None and verdict_for has no
    # governor to consult.
    path = Path(args.config) if getattr(args, "config", None) else find_config(Path.cwd())
    cfg = load(path) if path is not None else None
    print(verdict_for(args.open, args.regressed, args.broken, args.uncovered,
                      args.divergent, cfg=cfg))
