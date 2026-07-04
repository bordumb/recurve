#!/usr/bin/env bash
# ST-6: stalled but already on the best item -> CONTINUE (do not pivot off the best onto itself/nothing).
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
    verdict, item = pick_next(frontier, current_id="high", stalled=True)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if verdict == Verdict.CONTINUE and item == "high":
    print("stalled but already on the best item -> CONTINUE (no pointless pivot)")
    sys.exit(0)
print(f"ours=({verdict}, {item}) oracle=(CONTINUE, high) (a stalled best item is a REVERT call, not a pivot)")
sys.exit(1)
PYEOF
