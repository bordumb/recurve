#!/usr/bin/env bash
# CL-19: a public def nested in a conditional (if/for/try) body is still surfaced.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
SRC = ("import typing\n"
       "class C:\n"
       "    if typing.TYPE_CHECKING:\n"
       "        def guarded(self): ...\n"
       "    def real(self): pass\n")
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("strap", Path(fixture) / "broken_surface.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract = mod.extract
    else:
        from recurvelib.surface import PythonAdapter
        extract = PythonAdapter().extract
    ids = {p.id for p in extract(SRC, "t.py")}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"C.guarded", "C.real"}:
    print("a TYPE_CHECKING-guarded method is surfaced alongside the plain one: C.guarded, C.real")
    sys.exit(0)
print(f"ours={sorted(ids)} oracle={{'C.guarded','C.real'}} (a conditionally-defined method is still surface)")
sys.exit(1)
PYEOF
