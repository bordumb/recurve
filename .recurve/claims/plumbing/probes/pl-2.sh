#!/usr/bin/env bash
# PL-2: `recurve frontier` surfaces the completeness frontier — its logic
# (recurvelib.frontier_cli.frontier_ids) mirrors compute_frontier's ranked
# uncovered ids, so the loop/human can see what no claim covers. RED-first: until
# the surface exists the probe is RED; a surface that hides uncovered points is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.frontier import compute_frontier, SurfacePoint  # the oracle
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "ftrap", Path(fixture) / "broken_frontier.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        frontier_ids = mod.frontier_ids
    else:
        from recurvelib.analysis.frontier_cli import frontier_ids
except ImportError:
    print("ours=no `recurve frontier` surface yet oracle=frontier_ids mirrors compute_frontier")
    sys.exit(1)  # RED-first: the surface does not exist

cases = [
    ([("a", 1), ("b", 9), ("c", 5)], {"a"}, {"c"}),  # -> ["b"]
    ([("a", 1), ("b", 9), ("c", 5)], set(), set()),  # -> ["b","c","a"] (weight desc)
    ([("x", 2), ("y", 2)], set(), set()),            # -> ["x","y"] (tie -> id asc)
]
for pts, cov, dfr in cases:
    surface = [SurfacePoint(i, w) for i, w in pts]
    want = [p.id for p in compute_frontier(surface, cov, dfr).frontier]
    try:
        got = list(frontier_ids(surface, cov, dfr))
    except Exception as e:
        print(f"ours=frontier_ids raised {type(e).__name__} oracle={want}")
        sys.exit(1)
    if got != want:
        print(f"ours={got} oracle={want} for covered={sorted(cov)} deferred={sorted(dfr)}")
        sys.exit(1)

print("recurve frontier surfaces the frontier faithfully: frontier_ids mirrors compute_frontier")
sys.exit(0)
PYEOF
