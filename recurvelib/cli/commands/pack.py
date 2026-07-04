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

def cmd_pack(args):
    from recurvelib.io.pack import PackError, export_pack, install_pack
    cfg = _config(args)
    try:
        if args.action == "export":
            dest = export_pack(cfg, args.suite, Path(args.out), version=args.version)
            print(f"exported pack to {dest} — drafts only; receivers measure for themselves.")
        else:
            for n in install_pack(cfg, Path(args.path), args.suite):
                print(f"  - {n}")
    except PackError as e:
        _fail(str(e))
