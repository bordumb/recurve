#!/usr/bin/env bash
# AP-5: CommandActor surfaces a misbehaving agent as AgentError, never a crash or a silent no-change.
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
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        CommandActor = mod.CommandActor
    else:
        from recurvelib.adapters import CommandActor

    def outcome(cmd):
        try:
            CommandActor(cmd).propose("c", None, {})
            return "returned"            # no error raised
        except AgentError:
            return "AgentError"
        except Exception as e:
            return f"raw {type(e).__name__}"

    malformed = outcome(["python3", "-c", "print('I will fix it boss')"])   # not JSON
    nonzero = outcome(["python3", "-c", "import sys; sys.exit(3)"])          # crashed agent, empty stdout
    clean_empty = CommandActor(["python3", "-c", "import sys; sys.stdin.read()"]).propose("c", None, {})
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if malformed == "AgentError" and nonzero == "AgentError" and clean_empty == {}:
    print("malformed output and non-zero exit both -> AgentError; a clean empty run -> {} (no change)")
    sys.exit(0)
print(f"ours=(malformed={malformed}, nonzero={nonzero}, clean_empty={clean_empty}) "
      f"oracle=(AgentError, AgentError, {{}}) (a crash or a silent {{}} hides a broken agent)")
sys.exit(1)
PYEOF
