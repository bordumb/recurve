#!/usr/bin/env bash
# AP-3: CommandActor invokes the external command and returns its parsed patch (empty stdout -> no change).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        CommandActor = mod.CommandActor
    else:
        from recurvelib.adapters import CommandActor

    emit = CommandActor(["python3", "-c",
                         "import json,sys; json.load(sys.stdin); print(json.dumps({'x':'from-command'}))"])
    patch = emit.propose("contract", None, {"open": 1})

    silent = CommandActor(["python3", "-c", "import sys; sys.stdin.read()"])   # reads input, prints nothing
    empty = silent.propose("contract", None, {})
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if patch == {"x": "from-command"} and empty == {}:
    print("actor returns the command's parsed patch; empty stdout -> no change ({})")
    sys.exit(0)
print(f"ours=(command->{patch}, silent->{empty}) oracle=({{'x':'from-command'}}, {{}}) "
      f"(an actor that ignores the command is no longer driven by the agent)")
sys.exit(1)
PYEOF
