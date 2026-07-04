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

def cmd_lock(args):
    from ...lock import LockHeld, TreeLock, read_lock
    cfg = _config(args)
    tree = cfg.tree or cfg.root
    if args.action == "status":
        holder = read_lock(tree)
        if holder is None:
            print(f"unlocked — no loop holds {cfg.tree_display}")
        else:
            print(f"LOCKED by {holder.describe()}")
            raise SystemExit(1)
    elif args.action == "acquire":
        # For orchestrators that span many CLI invocations: the lock file
        # outlives this process; pair every acquire with a release.
        try:
            TreeLock(tree).acquire()
        except LockHeld as e:
            _fail(f"\033[31m✗ {e}\033[0m", 1)
        print(f"acquired — this run is the single loop on {cfg.tree_display}; "
              f"release when the run ends")
    elif args.action == "release":
        holder = read_lock(tree)
        if holder is None:
            print("nothing to release — the tree was not locked.")
        else:
            TreeLock(tree).steal()
            print(f"released {cfg.tree_display}")
    elif args.action == "steal":
        holder = TreeLock(tree).steal()
        if holder is None:
            print("nothing to steal — the tree was not locked.")
        else:
            print(f"stole the lock from {holder.describe()} — only do this when the "
                  f"holder is confirmed dead; two loops on one tree corrupt both.")
