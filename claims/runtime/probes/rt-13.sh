#!/usr/bin/env bash
# RT-13: an already-green world stops with STOP_SUCCESS before the actor is ever invoked (A1).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress, Verdict
    from recurvelib.admission import Assertion, admit
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run = mod.run
    else:
        from recurvelib.runtime import run

    class GreenWorld:
        def gate(self):
            return Progress(open=0, regressed=0, broken=0, uncovered=0)
        def apply(self, diff):
            pass
        def checkpoint(self):
            return 0
        def restore(self, snap):
            pass

    class Spy:
        def __init__(self):
            self.called = False
        def propose(self, c, i, e):
            self.called = True
            return None

    admit_rep = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True)])
    spy = Spy()
    v, _ = run(GreenWorld(), spy, admit_rep, "contract")
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v is Verdict.STOP_SUCCESS and not spy.called:
    print("already-green world -> STOP-SUCCESS on entry, the actor is never invoked on done code")
    sys.exit(0)
print(f"ours=(verdict={v}, actor_called={spy.called}) oracle=(STOP_SUCCESS, not called) "
      f"(suppressing first-cycle success runs the actor against already-done code)")
sys.exit(1)
PYEOF
