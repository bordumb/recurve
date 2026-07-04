#!/usr/bin/env bash
# AD-2: gateability is the measured probe-able share (probeable/total), 0.0 for an empty goal.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.admission import Assertion
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        gateability = mod.gateability
    else:
        from recurvelib.analysis.admission import gateability

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    half = [A("1", True, True, True), A("2", True, True, True), A("3", False, True, True), A("4", True, False, True)]
    g = gateability(half)       # 2 of 4 probe-able
    empty = gateability([])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if g == 0.5 and empty == 0.0:
    print("gateability = probeable/total: 0.5 for 2-of-4, 0.0 for empty")
    sys.exit(0)
print(f"ours=(half={g}, empty={empty}) oracle=(0.5, 0.0) (a fixed/inflated score is the vibe-check to avoid)")
sys.exit(1)
PYEOF
