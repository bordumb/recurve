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

def cmd_ledger(args):
    from ... import render
    cfg = _config(args)
    print(render.ledger_table(_load(cfg), cfg.label))
