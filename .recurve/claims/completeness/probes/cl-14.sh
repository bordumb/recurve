#!/usr/bin/env bash
# CL-14: all goal-counterexamples rejected -> not divergent (no false alarm that blocks real progress).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.fidelity import GoalCounterexample
    if fixture:
        spec = importlib.util.spec_from_file_location("ftrap", Path(fixture) / "broken_fidelity.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        divergent = mod.divergent
    else:
        from recurvelib.fidelity import divergent

    goals = [GoalCounterexample("a", accepted=False), GoalCounterexample("b", accepted=False)]
    result = divergent(goals)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result is False:
    print("all goal-counterexamples rejected -> not divergent (intent intact, progress allowed)")
    sys.exit(0)
print(f"ours=divergent {result} oracle=False (a false divergence alarm would force endless reverts)")
sys.exit(1)
PYEOF
