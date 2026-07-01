#!/usr/bin/env bash
# CL-24: covered_by unions the surface points ANY exercise runs; a point no exercise runs is not covered.
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
        covered_by = mod.covered_by
    else:
        from recurvelib.measured import covered_by

    def fa():
        return 1

    def fb():
        return 2

    def fc():
        return 3

    # exercise 1 runs fa, exercise 2 runs fb; fc is exercised by nothing.
    covered = covered_by([lambda: fa(), lambda: fb()], {"fa", "fb", "fc"})
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if covered == {"fa", "fb"}:
    print("covered_by = union of exercised points {fa, fb}; the un-run fc is not covered")
    sys.exit(0)
print(f"ours={sorted(covered)} oracle=['fa','fb'] (declaring the whole surface covered hides the un-run fc)")
sys.exit(1)
PYEOF
