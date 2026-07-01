#!/usr/bin/env bash
# RT-10: the guard refuses every non-ADMIT verdict, including REFUSE-AND-INTERVIEW (A6).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion, admit, Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        guarded_propose = mod.guarded_propose
    else:
        from recurvelib.runtime import guarded_propose

    # a gateable spine (2 probe-able) but a vague third -> REFUSE-AND-INTERVIEW, NOT admitted.
    report = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True),
                    Assertion("c", "", False, True, True)])

    class Spy:
        def __init__(self):
            self.called = False
        def propose(self, c, i, e):
            self.called = True
            return "diff"

    spy = Spy()
    r = guarded_propose(spy, report, None, None, None)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if report.verdict is Verdict.REFUSE_AND_INTERVIEW and r is None and not spy.called:
    print("REFUSE-AND-INTERVIEW contract: actor never called, guard returns None")
    sys.exit(0)
print(f"ours=(verdict={report.verdict.value}, returned={r!r}, called={spy.called}) oracle=(None, not called) "
      f"(keying on probeable count reaches the actor on a vague, non-admitted contract)")
sys.exit(1)
PYEOF
