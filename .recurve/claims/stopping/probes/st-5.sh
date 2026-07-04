#!/usr/bin/env bash
# ST-5: stalled on a lower-value item with a higher-value one available -> PIVOT to the higher.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Verdict
    from recurvelib.frontier import SurfacePoint
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pick_next = mod.pick_next
    else:
        from recurvelib.controller import pick_next

    frontier = [SurfacePoint("high", 9), SurfacePoint("low", 1)]
    verdict, item = pick_next(frontier, current_id="low", stalled=True)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if verdict == Verdict.PIVOT and item == "high":
    print("stalled on 'low' with 'high' available -> PIVOT to high")
    sys.exit(0)
print(f"ours=({verdict}, {item}) oracle=(PIVOT, high) (re-allocate off a stalled lower-value item)")
sys.exit(1)
PYEOF
