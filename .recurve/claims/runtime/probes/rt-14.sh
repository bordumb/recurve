#!/usr/bin/env bash
# RT-14: capture rejects a trap that is neither RED-on-wrong nor GREEN-on-real (A5).
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
        capture = mod.capture
    else:
        from recurvelib.runtime import capture

    neither = capture(False, False)   # green on wrong (catches nothing) AND red on real (breaks real): nonsense
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if neither is False:
    print("capture(False, False) -> False: a trap that catches nothing and breaks real is not evidence")
    sys.exit(0)
print(f"ours=capture(False,False)={neither} oracle=False (an XNOR capture accepts this nonsense trap)")
sys.exit(1)
PYEOF
