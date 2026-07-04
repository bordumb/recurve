#!/usr/bin/env bash
# CL-12: an uncovered point is surfaced on the frontier AND flags the cycle incomplete (no masking).
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
        spec = importlib.util.spec_from_file_location("cmptrap", Path(fixture) / "broken_completeness.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        completeness_report = mod.completeness_report
    else:
        from recurvelib.completeness import completeness_report

    surface = [SurfacePoint("a", 3), SurfacePoint("b", 2), SurfacePoint("c", 1)]
    rep = completeness_report(surface, covered={"a"}, deferred_ids={"b"})
    ids = {p.id for p in rep.frontier}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"c"} and rep.complete is False:
    print("the uncovered point 'c' is on the frontier and the cycle is flagged incomplete — no masking")
    sys.exit(0)
print(f"ours=frontier {sorted(ids)}, complete={rep.complete} oracle=frontier {{'c'}}, complete=False "
      f"(a hidden hole is the cardinal sin: a green gate that says nothing about 'c')")
sys.exit(1)
PYEOF
