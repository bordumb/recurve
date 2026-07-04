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

def cmd_import(args):
    cfg = _config(args)
    sc = cfg.suites.get(args.suite)
    if sc is None:
        _fail(f"unknown {cfg.label} {args.suite!r}; configured: {', '.join(cfg.suites)}")
    gaps_md = sc.dir / "GAPS.md"
    if not gaps_md.exists():
        _fail(f"no GAPS.md in {sc.dir}")
    prefix = args.prefix or "".join(w[0] for w in args.suite.split("-")).upper()
    imported = parse_gaps_md(gaps_md.read_text())
    skeleton = to_yaml_skeleton(args.suite, prefix, imported, prog=args.prog)
    # Drafts live in gaps.draft.yaml — the strict ledger (gaps.yaml) only ever
    # holds AUTHORED gaps with real class/severity/probe. Entries graduate via
    # the baseline ceremony.
    out = sc.dir / "gaps.draft.yaml"
    if out.exists() and not args.force:
        _fail(f"{out} exists — pass --force to overwrite (it merges nothing)")
    out.write_text(skeleton)
    print(f"wrote {out} ({len(imported)} gaps, prefix {prefix}) — "
          f"author probes, then graduate each entry into {sc.name}/gaps.yaml")
