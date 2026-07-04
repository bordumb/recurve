#!/usr/bin/env bash
# CL-4: equal-weight frontier points are ordered by ascending id, deterministically.
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
        spec = importlib.util.spec_from_file_location("ftrap", Path(fixture) / "broken_frontier.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compute_frontier = mod.compute_frontier
    else:
        from recurvelib.analysis.frontier import compute_frontier

    # all equal weight: order is decided entirely by the id tiebreak. Input is reverse-sorted to
    # catch a stable sort that merely preserves input order.
    surface = [SurfacePoint("zzz", 5), SurfacePoint("mmm", 5), SurfacePoint("aaa", 5)]
    order = [p.id for p in compute_frontier(surface, covered_ids=set()).frontier]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if order == ["aaa", "mmm", "zzz"]:
    print("equal-weight ties ordered by ascending id, deterministically")
    sys.exit(0)
print(f"ours=tie order {order} oracle=ascending id ['aaa','mmm','zzz'] (nondeterministic frontier is unusable)")
sys.exit(1)
PYEOF
