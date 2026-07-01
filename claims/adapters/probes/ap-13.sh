#!/usr/bin/env bash
# AP-13: a hanging agent command times out into an AgentError, never an unbounded loop hang.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.adapters import AgentError
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        CommandActor = mod.CommandActor
    else:
        from recurvelib.adapters import CommandActor

    # a command that sleeps past the timeout, then would emit a patch.
    cmd = ["python3", "-c", "import time,json; time.sleep(3); print(json.dumps({'x':'late'}))"]
    try:
        CommandActor(cmd, timeout=1).propose("c", None, {})
        result = "returned"      # no timeout enforced
    except AgentError:
        result = "AgentError"
    except Exception as e:
        result = f"raw {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "AgentError":
    print("a command exceeding the timeout -> AgentError (the loop is not wedged by a hanging agent)")
    sys.exit(0)
print(f"ours={result} oracle=AgentError (no timeout means a hanging agent hangs the loop forever)")
sys.exit(1)
PYEOF
