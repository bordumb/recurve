#!/usr/bin/env bash
# RT-15: referee matching is component-aware (whole path segments), robust to a trailing slash or not.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        within_boundary = mod.within_boundary
    else:
        from recurvelib.loop.runtime import within_boundary

    sibling = within_boundary(["claims_backup/x"], "", ["claims/"])   # a sibling dir — allowed
    exact = within_boundary(["claims"], "", ["claims/"])             # a file named exactly claims — refused
    under_noslash = within_boundary(["claims/p"], "", ["claims"])    # under, root given without slash — refused
    sibling_noslash = within_boundary(["claims_backup/x"], "", ["claims"])  # sibling, no slash — still allowed
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if sibling is True and exact is False and under_noslash is False and sibling_noslash is True:
    print("referee matches whole components: sibling allowed, exact/under refused, trailing-slash-agnostic")
    sys.exit(0)
print(f"ours=(sibling={sibling}, exact={exact}, under_noslash={under_noslash}, sibling_noslash={sibling_noslash}) "
      f"oracle=(True, False, False, True) (bare startswith refuses siblings and admits an exact-name file)")
sys.exit(1)
PYEOF
