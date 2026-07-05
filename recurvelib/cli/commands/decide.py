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
    from recurvelib.analysis.decide_cli import verdict_for, verdict_for_configured

    # A config, when one resolves, brings [gate] governor= into the decision
    # (R5's live wiring) — the exact call templates/workflows/burndown.sh's
    # stop_verdict() already makes. `recurve decide` predates any project-
    # context requirement, so a standalone invocation with no recurve.toml
    # anywhere upward keeps working exactly as before (verdict_for, no
    # governor to consult).
    cfg = None
    path = Path(args.config) if getattr(args, "config", None) else find_config(Path.cwd())
    if path is not None:
        try:
            cfg = load(path)
        except ConfigError:
            cfg = None
    if cfg is None:
        print(verdict_for(args.open, args.regressed, args.broken, args.uncovered, args.divergent))
    else:
        print(verdict_for_configured(cfg, args.open, args.regressed, args.broken,
                                     args.uncovered, args.divergent))
