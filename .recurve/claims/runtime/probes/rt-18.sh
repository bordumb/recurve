#!/usr/bin/env bash
# RT-18: a degenerate referee root fails closed, and a "." (root) patch key is rejected.
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
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        within_boundary = mod.within_boundary
    else:
        from recurvelib.loop.runtime import within_boundary

    empty_referee = within_boundary(["anything/x"], "", [""])      # empty referee root -> protect everything
    root_referee = within_boundary(["x"], "", ["/"])               # "/" referee -> protect everything
    root_key = within_boundary([""], "", ["claims/"])              # "." (the tree root) is not a file target
    normal = within_boundary(["src/foo.py"], "", ["claims/"])      # a normal write still allowed
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if empty_referee is False and root_referee is False and root_key is False and normal is True:
    print("degenerate referee roots fail closed; the '.' root key is refused; a normal write still passes")
    sys.exit(0)
print(f"ours=(empty={empty_referee}, root={root_referee}, root_key={root_key}, normal={normal}) "
      f"oracle=(False, False, False, True) (a misconfigured referee that fails open leaves the surface unguarded)")
sys.exit(1)
PYEOF
