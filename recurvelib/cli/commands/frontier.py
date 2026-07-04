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

def cmd_frontier(args):
    """Print the ranked uncovered ids for a surface given on flags — what no
    claim covers, highest-risk first. A thin honest report over
    `frontier_cli.frontier_ids`, which mirrors `compute_frontier`."""
    from ...frontier_cli import frontier_ids
    surface = [_parse_point(s) for s in (args.point or [])]
    covered = set(args.covered or [])
    deferred = set(args.deferred or [])
    ids = frontier_ids(surface, covered, deferred)
    if not ids:
        print("frontier empty — every surface point is covered or deferred.")
        return
    for i in ids:
        print(i)
