#!/usr/bin/env bash
# CL-7: public top-level functions AND public methods each become a (qualified) surface point.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
SRC = "def alpha():\n    pass\n\nclass Beta:\n    def gamma(self):\n        pass\n"
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

if ids == {"alpha", "Beta.gamma"}:
    print("public function + public method both surfaced, qualified: alpha, Beta.gamma")
    sys.exit(0)
print(f"ours=surface {sorted(ids)} oracle={{'Beta.gamma','alpha'}} (methods must surface, not just top-level)")
sys.exit(1)
PYEOF
