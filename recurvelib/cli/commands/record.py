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

def cmd_record(args):
    import json as _json
    from recurvelib.io.records import RecordError, validate_run_record
    cfg = _config(args)
    path = cfg.state_dir / "records.jsonl"
    if args.action == "append":
        try:
            record = _json.loads(Path(args.file).read_text() if args.file else sys.stdin.read())
        except (OSError, _json.JSONDecodeError) as e:
            _fail(f"unreadable record: {e}")
        if args.run_id:
            record.setdefault("run_id", args.run_id)
        record.setdefault("project", cfg.name)
        try:
            validate_run_record(record)
        except RecordError as e:
            _fail(f"record rejected (the dataset stays clean or it is worthless): {e}", 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = _json.dumps(record, sort_keys=True)
        # Idempotent: both the agent (per RUN.md) and the loop (per burndown)
        # may append the same record — one observation lands once.
        if path.exists() and line in set(path.read_text().splitlines()):
            print(f"cycle {record.get('cycle', '?')} already recorded — skipped "
                  f"(append is idempotent)")
            return
        with path.open("a") as f:
            f.write(line + "\n")
        print(f"recorded cycle {record.get('cycle', '?')} status={record.get('status')}")
    else:  # list
        if not path.exists():
            print("no run records yet.")
            return
        for line in path.read_text().splitlines():
            r = _json.loads(line)
            print(f"{r.get('finished_at', r.get('started_at', '?')):<22} "
                  f"{r.get('run_id', ''):<16} {r.get('cycle', ''):<18} "
                  f"{r.get('status', ''):<13} gap={r.get('gap', '')} "
                  f"attempts={r.get('attempts')} net_new={r.get('net_new_gaps', 0)}")
