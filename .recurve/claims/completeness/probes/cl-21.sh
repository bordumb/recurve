#!/usr/bin/env bash
# CL-21: surface points carry a meaningful weight (a complex unit outranks a trivial one).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
SRC = ("def small():\n    return 1\n"
       "def big():\n    a = 1\n    for i in range(5):\n        a += i\n    return a\n")
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("strap", Path(fixture) / "broken_surface.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract = mod.extract
    else:
        from recurvelib.analysis.surface import PythonAdapter
        extract = PythonAdapter().extract
    w = {p.id: p.weight for p in extract(SRC, "t.py")}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if w.get("big", 0) > w.get("small", 0) > 0:
    print(f"weights are meaningful: big={w['big']} > small={w['small']} > 0 (ranking is not vacuous)")
    sys.exit(0)
print(f"ours={w} oracle=big > small > 0 (a constant weight collapses frontier ranking to alphabetical)")
sys.exit(1)
PYEOF
