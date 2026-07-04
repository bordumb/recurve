#!/usr/bin/env bash
# CL-2: the frontier is ranked highest-risk (weight) first.
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

    surface = [SurfacePoint("low", 1), SurfacePoint("high", 9), SurfacePoint("mid", 5)]
    rep = compute_frontier(surface, covered_ids=set())
    order = [p.id for p in rep.frontier]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if order == ["high", "mid", "low"]:
    print("frontier ranked highest-weight first: ['high','mid','low']")
    sys.exit(0)
print(f"ours=frontier order {order} oracle=descending weight ['high','mid','low']")
sys.exit(1)
PYEOF
