#!/usr/bin/env bash
# CL-23: an empty surface is not "vacuously complete" (a measurement failure must not present as green).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("cmptrap", Path(fixture) / "broken_completeness.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        completeness_report = mod.completeness_report
    else:
        from recurvelib.completeness import completeness_report

    rep = completeness_report([], covered=set())  # nothing was extracted
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if rep.complete is False:
    print("empty surface -> complete=False (no surface is a measurement signal, not a finished cycle)")
    sys.exit(0)
print(f"ours=complete {rep.complete} oracle=False (a zero-surface 'complete' lets the controller STOP-SUCCESS on nothing)")
sys.exit(1)
PYEOF
