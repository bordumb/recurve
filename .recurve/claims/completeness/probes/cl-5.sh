#!/usr/bin/env bash
# CL-5: each surface point is classified per-occurrence; duplicate ids each count toward total.
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
        spec = importlib.util.spec_from_file_location("ftrap", Path(fixture) / "broken_frontier.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compute_frontier = mod.compute_frontier
    else:
        from recurvelib.frontier import compute_frontier

    # two distinct points share id "d"; nothing is covered, so all three are real uncovered surface.
    surface = [SurfacePoint("d", 9), SurfacePoint("d", 9), SurfacePoint("r", 1)]
    rep = compute_frontier(surface, covered_ids=set())
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if rep.total == 3 and rep.uncovered == 3:
    print("duplicate ids each count: total=3, none erased from the accounting")
    sys.exit(0)
print(f"ours=total {rep.total}, uncovered {rep.uncovered} oracle=3/3 (a deduping impl erases a real "
      f"uncovered point — a silent coverage hole)")
sys.exit(1)
PYEOF
