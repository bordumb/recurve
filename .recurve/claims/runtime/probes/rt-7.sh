#!/usr/bin/env bash
# RT-7: Sense reads open/regressed/broken straight from the gate (A2/A3 sensing seam).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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
        sense = mod.sense
    else:
        from recurvelib.runtime import sense

    progress, _ = sense({"open": 1, "regressed": 2, "broken": 3}, [SurfacePoint("a")], {"a"}, [])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if (progress.open, progress.regressed, progress.broken) == (1, 2, 3):
    print("Sense passes the gate counts through: open=1, regressed=2, broken=3")
    sys.exit(0)
print(f"ours=({progress.open},{progress.regressed},{progress.broken}) oracle=(1,2,3) "
      f"(hardcoding a gate field reads a RED world as green -> false STOP-SUCCESS)")
sys.exit(1)
PYEOF
