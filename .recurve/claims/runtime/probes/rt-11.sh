#!/usr/bin/env bash
# RT-11: the last-green floor is recorded only on a fully-clean cycle (open==regressed==broken==0) (A1).
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

    class Scripted:
        def __init__(self, readings):
            self.readings = readings
            self.cycle = 0
            self.restored_to = None
        def gate(self):
            return self.readings[min(self.cycle, len(self.readings) - 1)]
        def apply(self, diff):
            self.cycle += 1
        def checkpoint(self):
            return self.cycle
        def restore(self, snap):
            self.restored_to = snap

    class Noop:
        def propose(self, c, i, e):
            return None

    admit_rep = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True)])
    # cycle 0: sound-but-incomplete (a legit floor); cycle 1: REGRESSED (must NOT become the floor); then thrash.
    readings = [Progress(open=0, regressed=0, broken=0, uncovered=1),
                Progress(open=0, regressed=1, broken=0, uncovered=0),
                Progress(open=5, regressed=0, broken=0, uncovered=0),
                Progress(open=5, regressed=0, broken=0, uncovered=0)]
    w = Scripted(readings)
    v, _ = run(w, Noop(), admit_rep, "contract")
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v is Verdict.STOP_REVERT and w.restored_to == 0:
    print("revert restores the initial clean floor (cycle 0), never the regressed cycle 1")
    sys.exit(0)
print(f"ours=(verdict={v}, restored_to={w.restored_to}) oracle=(STOP_REVERT, 0) "
      f"(a floor keyed on open==0 alone would checkpoint the regressed cycle and revert to it)")
sys.exit(1)
PYEOF
