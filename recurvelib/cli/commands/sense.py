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

def cmd_sense(args):
    """Print the full measured progress vector for a surface given on flags —
    gate counts plus the uncovered (completeness) and divergent (fidelity)
    signals, exactly as the loop senses it for the controller. A thin honest
    report over `sense_cli.sense_vector`, which mirrors `runtime.sense`."""
    from ...sense_cli import sense_vector
    gate = {"open": args.open, "regressed": args.regressed, "broken": args.broken}
    surface = [_parse_point(s) for s in (args.point or [])]
    covered = set(args.covered or [])
    deferred = set(args.deferred or [])
    goals = [_parse_goal(s) for s in (args.goal or [])]
    v = sense_vector(gate, surface, covered, goals, deferred)
    print(f"open       {v['open']}")
    print(f"regressed  {v['regressed']}")
    print(f"broken     {v['broken']}")
    print(f"uncovered  {v['uncovered']}")
    print(f"divergent  {v['divergent']}")
