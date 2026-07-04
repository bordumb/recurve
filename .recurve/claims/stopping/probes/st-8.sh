#!/usr/bin/env bash
# ST-8: oscillating remaining-work reverts (dip-and-return is net-zero progress, not progress).
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

    # open dips 5 -> 1 then returns to 5: ends no lower than it started.
    osc = [Progress(open=5, regressed=0, broken=0, uncovered=0),
           Progress(open=1, regressed=0, broken=0, uncovered=0),
           Progress(open=5, regressed=0, broken=0, uncovered=0)]
    v = decide(osc)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.STOP_REVERT:
    print("oscillation [5,1,5] -> STOP-REVERT (no net progress is non-progress)")
    sys.exit(0)
print(f"ours={v} oracle=STOP-REVERT (a dip-and-return window loops forever if it escapes the revert)")
sys.exit(1)
PYEOF
