#!/usr/bin/env bash
# AD-15: an oscillating stuck history (dip then return) escalates, not loops forever.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion, InterviewVerdict
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        interview_step = mod.interview_step
    else:
        from recurvelib.admission import interview_step

    def vague(n):
        return [Assertion(f"a{i}", "", False, True, True) for i in range(n)]

    # un-probe-able count 2 -> 1 -> 2: dips, then the human re-introduces the gap. Net: no progress.
    history = [vague(2), vague(1), vague(2)]
    v = interview_step(history)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.ESCALATE:
    print("oscillating [2,1,2] -> ESCALATE (dip-and-return is not progress; never loops forever)")
    sys.exit(0)
print(f"ours={v} oracle=ESCALATE (escalating only on a strictly-flat window loops forever on [2,1,2,1,...])")
sys.exit(1)
PYEOF
