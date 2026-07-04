#!/usr/bin/env bash
# RT-5: the capture rule only accepts a discriminating trap (A5).
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
        from recurvelib.loop.runtime import capture

    discriminating = capture(True, True)    # RED on wrong, GREEN on real
    catches_nothing = capture(False, True)  # GREEN on wrong -> does not catch the bug
    breaks_real = capture(True, False)      # RED on real -> breaks the real impl
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if discriminating is True and catches_nothing is False and breaks_real is False:
    print("capture accepts only a discriminating trap (RED on wrong, GREEN on real)")
    sys.exit(0)
print(f"ours=(discriminating={discriminating}, catches_nothing={catches_nothing}, breaks_real={breaks_real}) "
      f"oracle=(True, False, False) (accepting a trap that catches nothing adds no evidence)")
sys.exit(1)
PYEOF
