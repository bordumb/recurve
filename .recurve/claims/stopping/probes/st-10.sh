#!/usr/bin/env bash
# ST-10: a non-stalled item is not pivoted away, even with a higher-value one waiting.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Verdict
    from recurvelib.analysis.frontier import SurfacePoint
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pick_next = mod.pick_next
    else:
        from recurvelib.loop.controller import pick_next

    frontier = [SurfacePoint("high", 9), SurfacePoint("low", 1)]
    # working "low", NOT stalled, even though "high" outranks it: stay put.
    result = pick_next(frontier, current_id="low", stalled=False)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == (Verdict.CONTINUE, "low"):
    print("non-stalled 'low' kept despite higher-value 'high' (pivot is for stuck items, not a re-sort)")
    sys.exit(0)
print(f"ours={result} oracle=(CONTINUE, 'low') (re-sorting onto 'high' every cycle thrashes the frontier)")
sys.exit(1)
PYEOF
