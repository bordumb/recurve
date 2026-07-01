#!/usr/bin/env bash
# RT-16: sense_measured feeds MEASURED coverage into the Progress vector (an un-run point is on the frontier).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.frontier import SurfacePoint
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sense_measured = mod.sense_measured
    else:
        from recurvelib.runtime import sense_measured

    def fa():
        return 1

    def fb():
        return 2

    def fc():
        return 3

    surface = [SurfacePoint("fa"), SurfacePoint("fb"), SurfacePoint("fc")]
    # exercises run fa and fb; fc is declared-able but exercised by nothing.
    progress, frontier = sense_measured({"open": 0, "regressed": 0, "broken": 0},
                                        surface, [lambda: fa(), lambda: fb()], [])
    ids = {p.id for p in frontier}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if progress.uncovered == 1 and ids == {"fc"}:
    print("sense derives coverage by tracing: fc (never run) is the measured-uncovered point on the frontier")
    sys.exit(0)
print(f"ours=(uncovered={progress.uncovered}, frontier={sorted(ids)}) oracle=(1, ['fc']) "
      f"(declaring the surface covered instead of tracing hides the un-run point from the gate)")
sys.exit(1)
PYEOF
