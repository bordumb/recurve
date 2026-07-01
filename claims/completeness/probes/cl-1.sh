#!/usr/bin/env bash
# CL-1: the frontier is exactly the uncovered surface (no covered/deferred point leaks in).
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
        spec = importlib.util.spec_from_file_location("ftrap", Path(fixture) / "broken_frontier.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compute_frontier = mod.compute_frontier
    else:
        from recurvelib.frontier import compute_frontier

    surface = [SurfacePoint("a", 5), SurfacePoint("b", 3), SurfacePoint("c", 1)]
    rep = compute_frontier(surface, covered_ids={"a"}, deferred_ids={"b"})
    ids = {p.id for p in rep.frontier}
except Exception as e:  # could not measure -> BROKEN, never a verdict
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"c"}:
    print("frontier is exactly the uncovered point — covered 'a' and deferred 'b' excluded")
    sys.exit(0)
print(f"ours=frontier admitted {sorted(ids)} oracle=only the uncovered {{'c'}} belongs")
sys.exit(1)
PYEOF
