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

def cmd_adjudicate(args):
    import time
    from recurvelib.io import render
    from recurvelib.io.adjudicate import adjudicate, retire
    C = render.C
    cfg = _config(args)
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        _fail(f"unknown gap id: {args.gap_id}")
    decision = args.decision
    if not decision and sys.stdin.isatty():
        print(f"{C['bold']}{g.id}{C['reset']}  {g.title}")
        print(f"  current smallest_fix: {g.smallest_fix[:120]}")
        decision = input("one sentence — the decision (empty aborts): ").strip()
    if not decision:
        _fail("no decision given — adjudication records a human sentence, never a guess")
    date = time.strftime("%Y-%m-%d")
    try:
        notes = (retire(cfg, g, decision, date) if args.retire
                 else adjudicate(cfg, g, decision, date))
    except GapParseError as e:
        _fail(str(e))
    for n in notes:
        print(f"  - {n}")
    verb = "retired" if args.retire else "adjudicated"
    print(f"{C['green']}✓ {g.id} {verb}{C['reset']} — three places, one decision; "
          f"run `{args.prog} validate && {args.prog} coverage` to confirm nothing drifted.")
