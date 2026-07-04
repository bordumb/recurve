#!/usr/bin/env bash
# CL-15: divergent_ids names exactly the accepted goal-counterexamples, highest weight first.
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
        divergent_ids = mod.divergent_ids
    else:
        from recurvelib.fidelity import divergent_ids

    goals = [
        GoalCounterexample("low", accepted=True, weight=1),
        GoalCounterexample("ok", accepted=False, weight=9),
        GoalCounterexample("high", accepted=True, weight=9),
    ]
    ids = divergent_ids(goals)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == ["high", "low"]:
    print("divergent_ids = exactly the accepted ones, worst first: ['high','low']")
    sys.exit(0)
print(f"ours={ids} oracle=['high','low'] (only accepted, ranked by weight so the revert names the worst)")
sys.exit(1)
PYEOF
