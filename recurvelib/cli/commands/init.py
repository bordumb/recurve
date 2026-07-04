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

def cmd_init(args):
    from recurvelib.io.init import infer_init_mode, run_init

    # An explicit mode flag always wins over the positional; --target likewise
    # wins over an inferred directory. The positional is a convenience that
    # resolves to one of the three explicit modes, and we ALWAYS say which.
    explicit_mode = args.from_prd or args.from_repo
    from_repo = args.from_repo
    from_prd = args.from_prd
    target = Path(args.target).resolve()

    if args.path is not None:
        pos = Path(args.path)
        mode, reason = infer_init_mode(pos)
        if explicit_mode:
            chose = "from-prd" if args.from_prd else "from-repo"
            print(f"inferred: {mode} ({reason}) — overridden: --{chose} was given explicitly, "
                  f"the flag wins")
        else:
            print(f"inferred: {mode} ({reason}) — use --from-repo/--from-prd/blank to override")
            if mode == "from-prd":
                from_prd = str(pos)
            elif mode == "from-repo":
                from_repo = True
                target = pos.resolve()
            else:  # blank
                target = pos.resolve()

    name = args.name or target.name
    suite = args.suite or ("claims" if from_prd else "core")
    try:
        notes = run_init(target, name=name, suite=suite, tree=args.tree,
                         label=args.label, quality=args.quality, prog=args.prog,
                         from_repo=from_repo)
    except FileExistsError as e:
        _fail(str(e))
    if from_prd:
        from recurvelib.analysis.claimify import run_claimify
        notes += run_claimify(target, Path(from_prd), suite=suite,
                              prog=args.prog, skip_review=args.no_review)
    print(f"initialized {name} at {target}")
    for n in notes:
        print(f"  - {n}")
    print(f"next: edit recurve.toml ([target] tree, [reads.*], rebuild), write claims, "
          f"author probes + traps, then `{args.prog} baseline {suite}`.")
