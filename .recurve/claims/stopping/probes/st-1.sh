#!/usr/bin/env bash
# ST-1: a fully-green cycle stops with success (the controller does not run past done).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Verdict, Progress
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        decide = mod.decide
    else:
        from recurvelib.controller import decide

    green = Progress(open=0, regressed=0, broken=0, uncovered=0, divergent=False)
    v = decide([green])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.STOP_SUCCESS:
    print("a fully-green cycle -> STOP-SUCCESS")
    sys.exit(0)
print(f"ours={v} oracle=STOP-SUCCESS (a controller that never stops on success is the core 'cannot stop' bug)")
sys.exit(1)
PYEOF
