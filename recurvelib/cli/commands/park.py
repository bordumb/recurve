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

def cmd_park(args):
    import time
    from recurvelib.io import render
    from recurvelib.loop.parked import ParkedStore
    C = render.C
    cfg = _config(args)
    store = ParkedStore(cfg.root)
    if not args.gap_id:
        parked = store.list()
        if not parked:
            print("nothing parked.")
            return
        for p in parked:
            print(f"{C['amber']}{p.gap}{C['reset']}  parked {p.parked_at} — {p.reason}")
            for a in p.attempts:
                print(render.dim(f"    attempt {a.get('at', '?')}: {a.get('tried', '')} "
                                 f"→ {a.get('observed', '')}"))
        return
    if args.unpark:
        if store.unpark(args.gap_id):
            print(f"unparked {args.gap_id} — it is triage-eligible again.")
        else:
            _fail(f"{args.gap_id} is not parked")
        return
    if _load(cfg).by_id(args.gap_id) is None:
        _fail(f"unknown gap id: {args.gap_id}")
    now = time.strftime("%Y-%m-%d")
    attempt = None
    if args.attempt:
        attempt = {"at": now, "tried": args.attempt, "observed": args.observed or ""}
    if args.reason:
        store.park(args.gap_id, args.reason, now, attempt)
        print(f"parked {args.gap_id} — the loop continues past it; humans triage parked gaps.")
    elif attempt:
        if not store.add_attempt(args.gap_id, attempt):
            _fail(f"{args.gap_id} is not parked — pass --reason to park it")
        print(f"recorded attempt on parked {args.gap_id} (observations, never conclusions).")
    else:
        _fail("pass --reason to park, --attempt to journal, or --unpark to release")
