#!/usr/bin/env bash
# AP-8: _jsonable is total — an object whose __str__ raises still serializes to a string.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _jsonable = mod._jsonable
    else:
        from recurvelib.adapters import _jsonable

    class Weird:
        def __str__(self):
            raise RuntimeError("boom")

    try:
        result = _jsonable(Weird())
        ok = isinstance(result, str)
    except Exception:
        ok = False
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ok:
    print("an object whose __str__ raises still serializes to a placeholder string")
    sys.exit(0)
print("ours=_jsonable re-raised oracle=a string (a non-total fallback crashes propose before the agent runs)")
sys.exit(1)
PYEOF
