#!/usr/bin/env bash
# TK-18: `recurve run` defaults the agent to a bypass-permissions Claude when
# AGENT_CMD is unset and no --agent is given — an unattended loop must never be
# left with an agent that stalls on a permission prompt. RED-first: a resolver
# that defaults to an empty or a prompting agent is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_run.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        resolve_agent = mod.resolve_agent
    else:
        from recurvelib.loop.run import resolve_agent
    agent, source = resolve_agent(None, None)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

ok = source == "default" and ("bypassPermissions" in agent or "--dangerously-skip-permissions" in agent)
if ok:
    print(f"unset AGENT_CMD -> {agent!r} [{source}] — the loop never stalls on a permission prompt")
    sys.exit(0)
print(f"ours=({agent!r}, {source!r}) oracle=a bypass-permissions default agent when AGENT_CMD is unset")
sys.exit(1)
PYEOF
