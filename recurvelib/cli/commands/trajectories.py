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

def cmd_trajectories(args):
    """Export the run-log as a verification-gated JSONL dataset: one object per
    cycle record on stdout, each row joining the record with its gap's ledger
    entry and naming the reward's provenance (which probe decides it, how many
    trap fixtures back it). A row is *verified* iff its gap still has a probe
    and at least one non-waived trap fixture; unverified rows are excluded by
    default and re-admitted only by --include-unverified, marked
    `"verified": false` — a reward that cannot be re-verified is a training
    hazard, not a datum. Read-only and deterministic: stable row sort and
    sorted keys make two exports of the same state byte-identical."""
    import json as _json
    import sys as _sys
    from ...report import load_records
    cfg = _config(args)
    ledger = _load(cfg)
    gaps = {g.id: g for g in ledger.gaps}
    records = load_records(cfg, args.suite or None)
    rows, excluded = [], 0
    for r in records:
        g = gaps.get(r.get("gap"))
        probe = g.probe if g else None
        traps = len(g.traps) if g else 0
        verified = bool(g and probe is not None and traps > 0 and not g.trap_waiver)
        if not verified and not args.include_unverified:
            excluded += 1
            continue
        rows.append({
            "gap": r.get("gap"), "suite": r.get("suite"),
            "action": r.get("status"), "attempts": r.get("attempts", 0),
            "reward": 1 if r.get("status") == "closed" else 0,
            "files_touched": r.get("files_touched", []),
            "severity": r.get("severity"), "class": r.get("class"),
            "run_id": r.get("run_id"), "cycle": r.get("cycle"),
            "summary": r.get("summary", ""),
            "verified": verified,
            "branches": r.get("branches", []),
            "provenance": {
                "probe": str(probe) if probe else None,
                "traps": traps,
                "trap_waiver": bool(g.trap_waiver) if g else False,
            },
        })
    rows.sort(key=lambda x: (x["suite"] or "", x["gap"] or "",
                             x["run_id"] or "", x["cycle"] or ""))
    for row in rows:
        print(_json.dumps(row, sort_keys=True))
    print(f"trajectories: exported {len(rows)}, excluded {excluded} unverified"
          f"{'' if args.include_unverified else ' (--include-unverified to include)'}",
          file=_sys.stderr)
