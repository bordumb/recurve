#!/usr/bin/env bash
# ST-2: flat progress reverts (the controller does not thrash forever).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
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

    # three cycles, work never shrinks (open stays 5) -> not converging.
    flat = [Progress(open=5, regressed=0, broken=0, uncovered=0) for _ in range(3)]
    v = decide(flat)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.STOP_REVERT:
    print("three flat cycles -> STOP-REVERT (bounded non-progress, no infinite loop)")
    sys.exit(0)
print(f"ours={v} oracle=STOP-REVERT (a controller that continues on flat progress thrashes forever)")
sys.exit(1)
PYEOF
