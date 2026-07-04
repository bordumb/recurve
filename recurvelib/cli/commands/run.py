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

def cmd_run(args):
    """Run the burndown loop with sensible defaults — the friendly wrapper over
    the stamped workflow (`recurvelib.run`). Resolves the agent (defaulting to a
    bypass-permissions Claude so an unattended cycle never stalls on a prompt),
    the cap, and the script, then execs it. `--dry-run` prints the resolution
    and exits."""
    import os
    import subprocess

    from ...run import build_run, bypasses_permissions, materialize_workflow, resolve_agent

    cfg = _config(args)
    agent, source = resolve_agent(args.agent, os.environ.get("AGENT_CMD"))
    cap = args.cap if args.cap is not None else cfg.burndown_cap
    argv, overrides = build_run(cfg, agent, cap, args.lanes, args.parked,
                                caffeinate=not args.no_caffeinate)
    if argv is None:
        _fail(f"no burndown workflow found (no stamped .recurve/workflows/, no shipped "
              f"template) — run `{args.prog} init` in the target first", 1)
    script = Path(argv[-1])

    warn = "  \033[33m⚠ permissions bypassed\033[0m" if bypasses_permissions(agent) else ""
    lanes = f"   lanes: {args.lanes}" if args.lanes and args.lanes > 1 else ""
    print(f"agent: {agent}   [{source}]{warn}")
    print(f"cap: {cap}   script: {script.name}{lanes}")
    if args.dry_run:
        print(" ".join(argv))
        return

    # Interpolate the shipped template (if un-stamped) into a runnable script.
    runnable = materialize_workflow(cfg, script)
    argv = [str(runnable) if a == str(script) else a for a in argv]
    env = dict(os.environ)
    env.update(overrides)
    raise SystemExit(subprocess.run(argv, env=env).returncode)
