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

def cmd_report(args):
    import json as _json
    from ...report import NarratorError, gather, load_records, run_narrator, to_markdown
    cfg = _config(args)
    if args.suite and args.suite not in cfg.suites:
        _fail(f"unknown {cfg.label} {args.suite!r}; configured: {', '.join(cfg.suites)}")
    if args.narrate and not cfg.report_narrator:
        _fail(f"--narrate needs [report] narrator in {cfg.source_file.name} — none is configured")
    gaps = [g for g in _load(cfg).gaps if not args.suite or g.suite == args.suite]
    records = load_records(cfg, args.suite)
    data = gather(cfg, gaps, records, suite=args.suite)
    md = to_markdown(data)
    narrator_err = ""
    if args.narrate:
        try:
            prose = run_narrator(cfg.report_narrator, cfg.report_narrator_timeout,
                                 md, records)
            md += f"\n\n## Narrative\n\n{prose}"
            data["narrative"] = prose
        except NarratorError as e:
            narrator_err = str(e)
    text = _json.dumps(data, indent=2, sort_keys=True) if args.format == "json" else md
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a") as f:
            f.write(text + "\n")
        print(f"appended report to {out}")
    else:
        print(text)
    # A narrator failure costs the prose, never the report: the deterministic
    # output above was already emitted in full before we say so.
    if narrator_err:
        print(f"\033[31m✗ narrator failed:\033[0m {narrator_err} — "
              f"the deterministic report stands", file=sys.stderr)
        raise SystemExit(1)
