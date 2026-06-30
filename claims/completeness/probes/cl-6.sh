#!/usr/bin/env bash
# CL-6: covered/deferred count only ids present on the surface; coverage claimed for an absent id
# never inflates the accounting.
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

    # one real surface point "a"; covered carries two phantom ids that are not on the surface.
    surface = [SurfacePoint("a", 5)]
    rep = compute_frontier(surface, covered_ids={"a", "ghost1", "ghost2"})
    accounting = rep.covered + rep.deferred + rep.uncovered
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if rep.covered == 1 and accounting == rep.total == 1:
    print("phantom covered ids ignored: covered=1, accounting stays total (1)")
    sys.exit(0)
print(f"ours=covered {rep.covered}, parts {accounting} vs total {rep.total} oracle=phantom ids must not "
      f"inflate covered or break totality")
sys.exit(1)
PYEOF
