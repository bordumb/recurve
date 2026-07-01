#!/usr/bin/env bash
# CL-20: an unparseable target yields a defined empty surface, not an uncaught crash.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("strap", Path(fixture) / "broken_surface.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract = mod.extract
    else:
        from recurvelib.surface import PythonAdapter
        extract = PythonAdapter().extract
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    result = extract("def broken(:\n    pass", "t.py")  # invalid syntax
except Exception as e:
    # the claim is that extraction must not crash the pass on a bad file -> a raise is the failure (RED).
    print(f"ours=raised {e!r} oracle=[] (one unparseable file must not abort the completeness pass)")
    sys.exit(1)

if result == []:
    print("unparseable target -> [] : a defined empty surface, no crash")
    sys.exit(0)
print(f"ours={result} oracle=[] (an unparseable target has a defined empty surface)")
sys.exit(1)
PYEOF
