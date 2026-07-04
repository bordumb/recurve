#!/usr/bin/env bash
# CL-3: coverage accounting is total (covered+deferred+uncovered == total; uncovered == len(frontier)).
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

    surface = [SurfacePoint(x) for x in ("a", "b", "c", "d")]
    rep = compute_frontier(surface, covered_ids={"a"}, deferred_ids={"b"})
    sums = rep.covered + rep.deferred + rep.uncovered
    total_ok = sums == rep.total == 4
    len_ok = rep.uncovered == len(rep.frontier)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if total_ok and len_ok:
    print("accounting is total: covered+deferred+uncovered == total, uncovered == len(frontier)")
    sys.exit(0)
print(f"ours=covered{rep.covered}+deferred{rep.deferred}+uncovered{rep.uncovered}={sums} vs total{rep.total} "
      f"(len_ok={len_ok}) oracle=every point classified exactly once")
sys.exit(1)
PYEOF
