#!/usr/bin/env bash
# CL-11: a cycle is complete iff nothing is uncovered (the frontier is empty).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.frontier import SurfacePoint
    if fixture:
        spec = importlib.util.spec_from_file_location("cmptrap", Path(fixture) / "broken_completeness.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        completeness_report = mod.completeness_report
    else:
        from recurvelib.completeness import completeness_report

    surface = [SurfacePoint("a", 1)]
    incomplete = completeness_report(surface, covered=set())     # a is uncovered
    complete = completeness_report(surface, covered={"a"})       # a is covered
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if incomplete.complete is False and complete.complete is True:
    print("complete iff uncovered==0: incomplete when 'a' is uncovered, complete when covered")
    sys.exit(0)
print(f"ours=(uncovered->{incomplete.complete}, covered->{complete.complete}) oracle=(False, True)")
sys.exit(1)
PYEOF
