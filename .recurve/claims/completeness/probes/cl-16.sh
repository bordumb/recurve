#!/usr/bin/env bash
# CL-16: a surface function the exercise actually calls is recorded as covered.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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
        from recurvelib.analysis.measured import measure_coverage

    def target_a():
        return 1

    def target_b():
        return 2

    def exercise():
        target_a()  # only a is exercised

    measured = measure_coverage(exercise, {"target_a", "target_b"})
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if "target_a" in measured:
    print("the exercised function target_a is measured as covered")
    sys.exit(0)
print(f"ours={sorted(measured)} oracle=contains target_a (a function the probe ran must count as covered)")
sys.exit(1)
PYEOF
