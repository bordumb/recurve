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

def cmd_coverage(args):
    from ... import render
    C = render.C
    cfg = _config(args)
    reports = coverage(cfg, _load(cfg))
    total_orphans = 0
    print(f"{C['bold']}    {cfg.label:<30}covered  orphan  closed  ledger?{C['reset']}")
    for r in reports:
        total_orphans += len(r.orphans)
        mark = C["green"] if r.complete and r.has_ledger else C["amber"]
        print(f"  {mark}{'●' if r.complete else '≈'}{C['reset']} {r.suite[:29]:<29} "
              f"{len(r.covered):>7}  {len(r.orphans):>6}  {len(r.closed):>6}  "
              f"{'yes' if r.has_ledger else C['amber'] + 'NONE' + C['reset']}")
    orphan_suites = [r for r in reports if r.orphans]
    if orphan_suites:
        print(f"\n{C['amber']}prose gaps with no ledger entry (import + author a probe, then add `covers:`):{C['reset']}")
        for r in orphan_suites:
            for anchor, title in r.orphans:
                print(f"  {C['dim']}· {r.suite} §{anchor}  {title[:60]}{C['reset']}")
    print(f"\n{total_orphans} orphan prose gap(s) across {len(reports)} {cfg.label}s")
    if args.gate and total_orphans:
        raise SystemExit(1)
