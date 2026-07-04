#!/usr/bin/env bash
# CL-8: private functions/methods and private classes' methods are excluded (implementation, not surface).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
SRC = (
    "def _hidden():\n    pass\n"
    "def shown():\n    pass\n"
    "class Pub:\n    def _priv(self):\n        pass\n    def pub(self):\n        pass\n"
    "class _Secret:\n    def meth(self):\n        pass\n"
)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("strap", Path(fixture) / "broken_surface.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract = mod.extract
    else:
        from recurvelib.analysis.surface import PythonAdapter
        extract = PythonAdapter().extract
    ids = {p.id for p in extract(SRC, "t.py")}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"shown", "Pub.pub"}:
    print("privates excluded: only {shown, Pub.pub} surfaced (no _hidden, Pub._priv, _Secret.meth)")
    sys.exit(0)
print(f"ours=surface {sorted(ids)} oracle={{'Pub.pub','shown'}} (underscore names and private-class methods are not surface)")
sys.exit(1)
PYEOF
