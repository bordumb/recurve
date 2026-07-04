#!/usr/bin/env bash
# ST-11: a stale current_id (no longer on the frontier) is reconciled, not echoed back as CONTINUE.
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
    # "ghost" is not on the frontier (it was covered or never existed): do not keep working it.
    result = pick_next(frontier, current_id="ghost", stalled=False)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == (Verdict.PIVOT, "high"):
    print("stale 'ghost' reconciled to the real frontier -> (PIVOT, 'high')")
    sys.exit(0)
print(f"ours={result} oracle=(PIVOT, 'high') (echoing a non-frontier id keeps the loop on work that is gone)")
sys.exit(1)
PYEOF
