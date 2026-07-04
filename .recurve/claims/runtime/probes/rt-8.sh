#!/usr/bin/env bash
# RT-8: the boundary rejects a diff if ANY path touches the referee surface, not just the first (A4).
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

    # a clean file paired with a probe edit -- the referee path is second.
    mixed = within_boundary(["repo/src/foo.py", "repo/claims/x/probe.sh"], "repo/", ["repo/claims/"])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if mixed is False:
    print("a diff touching the referee surface anywhere in the list is rejected (all paths checked)")
    sys.exit(0)
print(f"ours={mixed} oracle=False (checking only the first path lets the actor slip a probe edit in beside a clean one)")
sys.exit(1)
PYEOF
