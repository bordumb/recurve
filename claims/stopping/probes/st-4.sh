#!/usr/bin/env bash
# ST-4: with no current item, the controller starts on the highest-value frontier point.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
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

    frontier = [SurfacePoint("high", 9), SurfacePoint("low", 1)]  # ranked, highest first
    verdict, item = pick_next(frontier, current_id=None)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if item == "high":
    print("starts on the highest-value frontier point: high")
    sys.exit(0)
print(f"ours=started on {item} oracle=high (work the most valuable uncovered point first)")
sys.exit(1)
PYEOF
