#!/usr/bin/env bash
# AD-3: the worklist names exactly the un-probe-able assertions with their specific gaps (never a probe-able one).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.admission import Assertion
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        worklist = mod.worklist
    else:
        from recurvelib.analysis.admission import worklist

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    good = A("good", True, True, True)
    bad1 = A("bad1", False, True, True)   # 1 gap: no oracle
    bad2 = A("bad2", True, False, False)  # 2 gaps: no counterexample, unbounded
    wl = worklist([good, bad1, bad2])
    ids = [item[0] for item in wl]
    gapcount = {item[0]: len(item[1]) for item in wl}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == ["bad1", "bad2"] and gapcount.get("bad1") == 1 and gapcount.get("bad2") == 2:
    print("worklist = the un-probe-able assertions only, each with its named gaps (bad1:1, bad2:2)")
    sys.exit(0)
print(f"ours=ids {ids}, gaps {gapcount} oracle=['bad1','bad2'] with 1 and 2 gaps; 'good' absent (not a score)")
sys.exit(1)
PYEOF
