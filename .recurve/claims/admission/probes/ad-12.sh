#!/usr/bin/env bash
# AD-12: the interview ESCALATEs when bounded rounds pass with no reduction in the un-probe-able set.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.admission import Assertion, InterviewVerdict
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        interview_step = mod.interview_step
    else:
        from recurvelib.analysis.admission import interview_step

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    # three rounds, the same two assertions stay vague -- the human cannot name the checks.
    stuck = [[A("a", False, True, True), A("b", False, True, True)] for _ in range(3)]
    v = interview_step(stuck)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.ESCALATE:
    print("three rounds, no reduction -> ESCALATE (not gateable; do not interview forever)")
    sys.exit(0)
print(f"ours={v} oracle=ESCALATE (an interview that never escalates loops forever on a goal that cannot be gated)")
sys.exit(1)
PYEOF
