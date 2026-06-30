#!/usr/bin/env bash
# AD-16: the no-progress window is the most recent max_rounds -- an early stuck stretch since converged continues.
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

    def vague(n):
        return [Assertion(f"a{i}", "", False, True, True) for i in range(n)]

    # stuck early (3,3,3) then actively converging (2,1): the recent window must win.
    history = [vague(3), vague(3), vague(3), vague(2), vague(1)]
    v = interview_step(history)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.CONTINUE:
    print("[3,3,3,2,1] -> CONTINUE (the recent window is converging; an old stuck stretch does not escalate)")
    sys.exit(0)
print(f"ours={v} oracle=CONTINUE (a front-of-history window abandons a goal that is actively gating)")
sys.exit(1)
PYEOF
