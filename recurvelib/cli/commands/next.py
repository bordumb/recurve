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

def cmd_next(args):
    import json as _json
    from ... import render
    from ...parked import ParkedStore
    C = render.C
    cfg = _config(args)
    prog = args.prog
    ledger = _load(cfg)
    auto, gated = triage(ledger, cfg)
    parked = ParkedStore(cfg.root).list()
    parked_ids = {p.gap for p in parked}
    auto = [g for g in auto if g.id not in parked_ids]
    gated = [g for g in gated if g.id not in parked_ids]
    open_gaps = auto + gated
    drafts, forks_pending = _draft_backlog(cfg)

    if getattr(args, "lanes", None):
        from ...triage import lanes as deal_lanes
        dealt = deal_lanes(ledger, cfg, args.lanes, exclude=parked_ids)
        if getattr(args, "json", False):
            print(_json.dumps({"lanes": [
                {"gap": g.id, "suite": g.suite, "title": g.title,
                 "class": g.gap_class.value, "severity": g.severity.value,
                 "dir": str(cfg.suites[g.suite].dir)}
                for g in dealt]}))
        else:
            for g in dealt:
                print(f"  lane {g.suite:<24} ▸ {g.id}  {g.title}")
            if not dealt:
                print("no lanes to deal — no workable open gaps.")
        return

    if getattr(args, "json", False):
        rec = auto[0] if auto else None
        print(_json.dumps({
            "recommended": ({"gap": rec.id, "suite": rec.suite, "title": rec.title,
                             "class": rec.gap_class.value, "severity": rec.severity.value}
                            if rec else None),
            "then": [g.id for g in auto[1:]],
            "review_gated": [g.id for g in gated],
            "parked": [{"gap": p.gap, "reason": p.reason} for p in parked],
            "drafts": drafts,
            "adjudications_pending": forks_pending,
        }))
        return

    if auto:
        top = auto[0]
        slug = "".join(c if c.isalnum() else "-" for c in top.title.lower())[:24].strip("-")
        print(f"{C['bold']}recommended next (highest value first; green gate is sufficient):{C['reset']}")
        print(f"  {C['green']}▸ {top.id}{C['reset']}  {top.title}")
        print(f"    {render.dim(top.suite + ' · ' + top.gap_class.value + ' · ' + top.severity.value)}")
        if top.unlocks:
            print(f"    {render.dim('unlocks: ' + top.unlocks.splitlines()[0])}")
        print(f"    scaffold: ./{prog} cycle new {slug or top.id.lower()} --gaps {top.id}")
        if len(auto) > 1:
            print(render.dim("  then: " + ", ".join(f"{g.id}({g.severity.value})" for g in auto[1:])))
    else:
        print(f"{C['amber']}no green-gate-sufficient open gaps remain.{C['reset']}")

    if gated:
        print(f"\n{C['amber']}review-gated — security-tradeoff (a green gate is NOT enough; "
              f"loosening a check can pass every probe and still open a hole):{C['reset']}")
        for g in gated:
            print(f"  {C['dim']}· {g.id}  {g.title}{C['reset']}")
        print(render.dim(f"  workable via the adversarial protocol: ./{prog} review {gated[0].id}  (then RUN.md §review-gated)"))

    if parked:
        print(f"\n{C['amber']}parked — run state awaiting human triage (the loop continues past these):{C['reset']}")
        for p in parked:
            print(f"  {C['dim']}· {p.gap}  {p.reason[:70]}{C['reset']}")

    if not open_gaps:
        print(f"{C['green']}✓ no open gaps — the backlog is clear for this ledger.{C['reset']}")
    if drafts:
        total = sum(d["pending"] for d in drafts)
        where = ", ".join(f"{d['suite']} ({d['pending']})" for d in drafts)
        print(f"\n{C['amber']}{total} draft claim(s) await the next wave:{C['reset']} {where}")
        if forks_pending:
            print(f"  {C['amber']}⚠ {forks_pending} fork(s) pending in ADJUDICATE.md — "
                  f"one human sentence each, before any baseline.{C['reset']}")
        print(render.dim(f"  arm them: author probes + traps, then ./{prog} baseline <suite> "
                         f"(the burndown loop arms waves itself)"))
