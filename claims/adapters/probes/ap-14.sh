#!/usr/bin/env bash
# AP-14: _jsonable is total for dataclasses too — a recursive dataclass still serializes to a string.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        _jsonable = mod._jsonable
    else:
        from recurvelib.adapters import _jsonable

    @dataclass
    class Bad:
        x: object

    b = Bad(x=None)
    b.x = b                       # self-referential field -> asdict deep-recurses

    try:
        result = _jsonable(b)
        ok = isinstance(result, str)
    except Exception:
        ok = False
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ok:
    print("a recursive dataclass serializes to a placeholder string (asdict failure is caught)")
    sys.exit(0)
print("ours=_jsonable raised on a recursive dataclass oracle=a string (the dataclass branch was unguarded)")
sys.exit(1)
PYEOF
