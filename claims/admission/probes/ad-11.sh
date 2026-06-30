#!/usr/bin/env bash
# AD-11: the interview ADMITs once the latest round is fully probe-able.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
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

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    # round 1: vague; round 2: the human named the check, now probe-able.
    history = [[A("x", False, True, True)], [A("x", True, True, True)]]
    v = interview_step(history)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.ADMIT:
    print("latest round fully probe-able -> ADMIT (the goal is now a contract)")
    sys.exit(0)
print(f"ours={v} oracle=ADMIT (an interview that never recognizes done runs past a finished contract)")
sys.exit(1)
PYEOF
