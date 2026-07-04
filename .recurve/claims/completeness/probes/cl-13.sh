#!/usr/bin/env bash
# CL-13: a single accepted goal-counterexample makes the cycle divergent (intent breach is not missed).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.fidelity import GoalCounterexample
    if fixture:
        spec = importlib.util.spec_from_file_location("ftrap", Path(fixture) / "broken_fidelity.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        divergent = mod.divergent
    else:
        from recurvelib.analysis.fidelity import divergent

    goals = [GoalCounterexample("ok", accepted=False), GoalCounterexample("bad", accepted=True)]
    result = divergent(goals)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result is True:
    print("an accepted goal-counterexample -> divergent (green probes cannot hide a broken intent)")
    sys.exit(0)
print(f"ours=divergent {result} oracle=True (a must-reject behavior was accepted)")
sys.exit(1)
PYEOF
