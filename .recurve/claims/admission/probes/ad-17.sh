#!/usr/bin/env bash
# AD-17: ADMIT wins over ESCALATE when the latest round just became fully probe-able at the round limit.
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

    ok_round = [Assertion("x", "", True, True, True)]               # fully probe-able -> 0 un-probe-able
    vague_round = [Assertion("a", "", False, True, True), Assertion("b", "", False, True, True)]
    # remaining = [0, 2, 0]: gated, regressed, just re-gated on the final round.
    history = [ok_round, vague_round, ok_round]
    v = interview_step(history)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == InterviewVerdict.ADMIT:
    print("[0,2,0] -> ADMIT (a contract that just re-gated is admitted, not escalated)")
    sys.exit(0)
print(f"ours={v} oracle=ADMIT (checking ESCALATE before ADMIT throws out a goal that is now fully probe-able)")
sys.exit(1)
PYEOF
