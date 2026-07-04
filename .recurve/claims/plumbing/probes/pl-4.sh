#!/usr/bin/env bash
# PL-4: `recurve sense` surfaces the measured progress vector — sense_vector
# assembles open/regressed/broken (gate) + uncovered (frontier) + divergent
# (fidelity) exactly as runtime.sense does, so the loop can feed the FULL vector
# to the controller. RED-first until the surface exists; a sense that drops the
# uncovered or divergent field is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.runtime import sense                 # the oracle
    from recurvelib.analysis.frontier import SurfacePoint
    from recurvelib.analysis.fidelity import GoalCounterexample
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "strap", Path(fixture) / "broken_sense.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        sense_vector = mod.sense_vector
    else:
        from recurvelib.analysis.sense_cli import sense_vector
except ImportError:
    print("ours=no `recurve sense` surface yet oracle=sense_vector mirrors runtime.sense")
    sys.exit(1)  # RED-first

# A target with an uncovered point (b) AND an accepted goal-counterexample.
gate = {"open": 2, "regressed": 1, "broken": 0}
surface = [SurfacePoint("a", 1), SurfacePoint("b", 9)]
covered = {"a"}
gcx = [GoalCounterexample("x", accepted=True, weight=5)]
prog, _ = sense(gate, surface, covered, gcx)
want = (prog.open, prog.regressed, prog.broken, prog.uncovered, prog.divergent)  # (2,1,0,1,True)
try:
    got = sense_vector(gate, surface, covered, gcx)
    gotv = ((got["open"], got["regressed"], got["broken"], got["uncovered"], got["divergent"])
            if isinstance(got, dict) else tuple(got))
except Exception as e:
    print(f"ours=sense_vector raised {type(e).__name__} oracle={want}")
    sys.exit(1)

if gotv == want:
    print(f"recurve sense mirrors runtime.sense (incl. uncovered + divergent): {gotv}")
    sys.exit(0)
print(f"ours={gotv} oracle={want} — sense_vector must mirror runtime.sense, uncovered + divergent included")
sys.exit(1)
PYEOF
