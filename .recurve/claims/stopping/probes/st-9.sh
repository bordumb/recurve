#!/usr/bin/env bash
# ST-9: an empty frontier yields a clean no-op, not a crash.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pick_next = mod.pick_next
    else:
        from recurvelib.controller import pick_next
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    result = pick_next([], current_id=None)
except Exception as e:
    # the claim is specifically that an empty frontier must not crash -> a raise is RED, not BROKEN.
    print(f"ours=raised {e!r} oracle=(CONTINUE, None) — frontier exhaustion must not crash the loop")
    sys.exit(1)

if result == (Verdict.CONTINUE, None):
    print("empty frontier -> (CONTINUE, None): a clean no-op at frontier exhaustion")
    sys.exit(0)
print(f"ours={result} oracle=(CONTINUE, None)")
sys.exit(1)
PYEOF
