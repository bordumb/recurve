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
    from ...decide_cli import verdict_for
    print(verdict_for(args.open, args.regressed, args.broken, args.uncovered, args.divergent))
