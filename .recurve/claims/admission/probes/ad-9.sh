#!/usr/bin/env bash
# AD-9: min_invariants is an inclusive floor -- a spine of exactly min_invariants is gateable.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.admission import Assertion, Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        admit = mod.admit
    else:
        from recurvelib.analysis.admission import admit

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    # spine == min_invariants == 2, exactly on the boundary.
    all_two = admit([A("1", True, True, True), A("2", True, True, True)]).verdict          # all probe-able
    mixed = admit([A("1", True, True, True), A("2", True, True, True), A("3", False, True, True)]).verdict
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if all_two == Verdict.ADMIT and mixed == Verdict.REFUSE_AND_INTERVIEW:
    print("spine == min (2): all-probe-able -> ADMIT, vague-remainder -> REFUSE-AND-INTERVIEW (inclusive floor)")
    sys.exit(0)
print(f"ours=(all={all_two}, mixed={mixed}) oracle=(ADMIT, REFUSE-AND-INTERVIEW) (off-by-one refuses valid minimum goals)")
sys.exit(1)
PYEOF
