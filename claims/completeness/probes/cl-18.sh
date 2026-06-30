#!/usr/bin/env bash
# CL-18: measured coverage is restricted to the surface (calls outside it are not phantom coverage).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("mtrap", Path(fixture) / "broken_measured.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        measure_coverage = mod.measure_coverage
    else:
        from recurvelib.measured import measure_coverage

    def target_a():
        return 1

    def helper():       # exercised, but NOT part of the declared surface
        return 99

    def exercise():
        target_a()
        helper()

    measured = measure_coverage(exercise, {"target_a"})  # surface is only target_a
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if measured == {"target_a"}:
    print("measured == {target_a}: the off-surface call 'helper' is not phantom coverage")
    sys.exit(0)
print(f"ours={sorted(measured)} oracle={{'target_a'}} (only surface points count; off-surface calls are dropped)")
sys.exit(1)
PYEOF
