#!/usr/bin/env bash
# RT-17: a raising probe body does not crash Sense — sense_measured still yields a Progress vector.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.frontier import SurfacePoint
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sense_measured = mod.sense_measured
    else:
        from recurvelib.loop.runtime import sense_measured

    def fa():
        return 1

    def fb():
        return 2

    def boom():
        raise ValueError("probe body errored")

    surface = [SurfacePoint("fa"), SurfacePoint("fb"), SurfacePoint("fc")]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    progress, frontier = sense_measured({"open": 0, "regressed": 0, "broken": 0},
                                        surface, [lambda: fa(), lambda: boom(), lambda: fb()], [])
    ids = {p.id for p in frontier}
except Exception as e:
    print(f"ours=Sense crashed on a raising exercise ({type(e).__name__}) oracle=a Progress with fc on the frontier")
    sys.exit(1)

if progress.uncovered == 1 and ids == {"fc"}:
    print("a raising probe body doesn't crash Sense: fa/fb measured covered, fc on the frontier")
    sys.exit(0)
print(f"ours=(uncovered={progress.uncovered}, frontier={sorted(ids)}) oracle=(1, ['fc'])")
sys.exit(1)
PYEOF
