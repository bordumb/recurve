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

def cmd_stats(args):
    import json as _json
    from recurvelib.io import render
    C = render.C
    cfg = _config(args)
    path = cfg.state_dir / "records.jsonl"
    if not path.exists():
        print("no run records yet — the dataset starts with the first cycle.")
        return
    records = [_json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    by_class: dict[str, list] = {}
    for r in records:
        by_class.setdefault(r.get("class") or "(unclassed)", []).append(r)
    # close%@k = closed within an attempt budget of k. Raw close% inflates
    # under retries; the budgeted columns make attempt inflation visible.
    print(f"{C['bold']}class               cycles  closed  parked  failed  close%  c%@1  c%@2  avg-attempts  avg-clock{C['reset']}")
    for cls, rs in sorted(by_class.items()):
        closed = sum(1 for r in rs if r.get("status") == "closed")
        parked = sum(1 for r in rs if r.get("status") == "parked")
        failed = sum(1 for r in rs if r.get("status") == "failed")
        rate = 100 * closed / len(rs) if rs else 0
        at1 = 100 * sum(1 for r in rs if r.get("status") == "closed"
                        and r.get("attempts", 0) <= 1) / len(rs) if rs else 0
        at2 = 100 * sum(1 for r in rs if r.get("status") == "closed"
                        and r.get("attempts", 0) <= 2) / len(rs) if rs else 0
        att = sum(r.get("attempts", 0) for r in rs) / len(rs)
        clk = sum(r.get("wall_clock_s", 0) for r in rs) / len(rs)
        print(f"{cls:<19} {len(rs):>6}  {closed:>6}  {parked:>6}  {failed:>6}  "
              f"{rate:>5.0f}%  {at1:>3.0f}%  {at2:>3.0f}%  {att:>12.1f}  {clk:>8.0f}s")
    total_closed = sum(1 for r in records if r.get("status") == "closed")
    regressions = sum(r.get("regressions_caught", 0) for r in records)
    # Verification debt belongs in the same view as the rates it qualifies: a
    # waived guard is a closed claim the drill cannot audit.
    try:
        waived = sum(1 for g in _load(cfg).gaps
                     if g.status is Status.CLOSED and g.trap_waiver)
        plural = "" if waived == 1 else "s"
        print(render.dim(f"\ntrap debt: {waived} waived guard{plural} "
                         f"(closed claims the drill cannot audit)"))
    except Exception:
        pass
    # AI8: the unified challenge_event rate — R4's reversal + R5's veto,
    # combined, sliceable by phase. 0/N on a ledger with no challenges.
    try:
        from recurvelib.adapters.challenge_event import ChallengeLog
        ledger = _load(cfg)
        total_closed = sum(1 for g in ledger.gaps if g.status is Status.CLOSED)
        suites = sorted({g.suite for g in ledger.gaps})
        events = [e for s in suites for e in ChallengeLog(cfg, s).events()]
        pre = sum(1 for e in events if e.get("phase") == "pre_publication")
        post = sum(1 for e in events if e.get("phase") == "post_publication")
        rate = (len(events) / total_closed) if total_closed else 0.0
        print(render.dim(
            f"challenge rate: {len(events)}/{total_closed} ({rate:.1%}) — "
            f"{pre} pre_publication (veto), {post} post_publication (reversal)"))
    except Exception:
        pass
    print(render.dim(
        f"\n{len(records)} cycle records · {total_closed} self-grading tasks accumulated "
        f"(snapshot + RED probe + gate-as-oracle) · {regressions} regression(s) caught at the gate"))
    print(render.dim("close-rate by class is triage prior material; the dataset is the product."))
