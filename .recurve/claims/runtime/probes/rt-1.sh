#!/usr/bin/env bash
# RT-1: the loop stops by the gate, never the actor's word (A1).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Progress, Verdict
    from recurvelib.analysis.admission import Assertion, admit
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run = mod.run
    else:
        from recurvelib.loop.runtime import run

    class Diff:
        def __init__(self, fixes, done=False):
            self.fixes = fixes
            self.done = done

    class StubWorld:
        def __init__(self, red):
            self.red = red
        def gate(self):
            return Progress(open=self.red, regressed=0, broken=0, uncovered=0)
        def apply(self, diff):
            self.red = max(0, self.red - diff.fixes)
        def checkpoint(self):
            return self.red
        def restore(self, snap):
            self.red = snap

    class FixingActor:
        def propose(self, c, i, e):
            return Diff(fixes=1)

    class LyingActor:
        def propose(self, c, i, e):
            return Diff(fixes=0, done=True)   # claims done, changes nothing

    admit_rep = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True)])

    w1 = StubWorld(red=1)
    v1, _ = run(w1, FixingActor(), admit_rep, "contract")
    happy = (v1 is Verdict.STOP_SUCCESS and w1.red == 0)

    w2 = StubWorld(red=1)
    v2, _ = run(w2, LyingActor(), admit_rep, "contract")
    honest = (v2 is not Verdict.STOP_SUCCESS)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if happy and honest:
    print("fixing actor -> STOP-SUCCESS + world green; lying actor -> never STOP-SUCCESS (verdict from the gate)")
    sys.exit(0)
print(f"ours=(fixing->{v1}, red={w1.red}; lying->{v2}) oracle=(STOP_SUCCESS+red0; lying NOT STOP_SUCCESS)")
sys.exit(1)
PYEOF
