#!/usr/bin/env bash
# AP-17: an agent command that cannot be executed surfaces as AgentError, not a raw FileNotFoundError.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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

    try:
        CommandActor(["/no/such/agent-binary-xyz"]).propose("c", None, {})
        result = "returned"
    except AgentError:
        result = "AgentError"
    except Exception as e:
        result = f"raw {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "AgentError":
    print("a not-found agent command -> AgentError (typed), not a raw FileNotFoundError")
    sys.exit(0)
print(f"ours={result} oracle=AgentError (catching only TimeoutExpired leaks a raw error on a missing binary)")
sys.exit(1)
PYEOF
