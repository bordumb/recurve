#!/usr/bin/env bash
# AD-13: the interview CONTINUEs while the un-probe-able set is still shrinking.
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

    # un-probe-able set shrinks 3 -> 2 -> 1 across three rounds: progress, not yet done.
    history = [vague(3), vague(2), vague(1)]
    v = interview_step(history)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.CONTINUE:
    print("un-probe-able set shrinking 3->2->1 -> CONTINUE (a converging interview is not abandoned)")
    sys.exit(0)
print(f"ours={v} oracle=CONTINUE (escalating while progress is being made gives up on a goal about to gate)")
sys.exit(1)
PYEOF
