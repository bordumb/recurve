#!/usr/bin/env bash
# RT-2: Sense reports the real uncovered work (A2).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.frontier import SurfacePoint
    from recurvelib.controller import pick_next
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sense = mod.sense
    else:
        from recurvelib.runtime import sense

    surface = [SurfacePoint("alpha", 5)]   # one public unit, nothing covered
    progress, frontier = sense({"open": 0, "regressed": 0, "broken": 0}, surface, set(), [])
    ids = [p.id for p in frontier]
    nxt = pick_next(frontier)[1] if frontier else None
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if progress.uncovered == 1 and ids == ["alpha"] and nxt == "alpha":
    print("Sense surfaces the uncovered unit: uncovered=1, frontier=['alpha'], pick_next -> alpha")
    sys.exit(0)
print(f"ours=(uncovered={progress.uncovered}, frontier={ids}, next={nxt}) oracle=(1, ['alpha'], 'alpha')")
sys.exit(1)
PYEOF
