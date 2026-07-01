#!/usr/bin/env bash
# RT-3: Sense feeds divergence, so a green-but-diverged cycle does not stop (A3).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.frontier import SurfacePoint
    from recurvelib.fidelity import GoalCounterexample
    from recurvelib.controller import decide, Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sense = mod.sense
    else:
        from recurvelib.runtime import sense

    # all probes green, surface fully covered, but a goal-counterexample was accepted -> diverged.
    surface = [SurfacePoint("alpha")]
    progress, _ = sense({"open": 0, "regressed": 0, "broken": 0}, surface, {"alpha"},
                        [GoalCounterexample("forbidden", accepted=True)])
    stops = decide([progress])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if progress.divergent is True and stops is not Verdict.STOP_SUCCESS:
    print("green-but-diverged cycle: divergent=True, decide != STOP-SUCCESS (intent breach blocks the stop)")
    sys.exit(0)
print(f"ours=(divergent={progress.divergent}, decide={stops}) oracle=(True, not STOP_SUCCESS)")
sys.exit(1)
PYEOF
