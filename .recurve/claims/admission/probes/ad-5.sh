#!/usr/bin/env bash
# AD-5: a gateable spine with a vague remainder -> REFUSE-AND-INTERVIEW, never ADMIT.
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

    # spine of 3 probe-able (>= min 2), but two assertions are still vague.
    mixed = [A("1", True, True, True), A("2", True, True, True), A("3", True, True, True),
             A("4", False, True, True), A("5", True, False, True)]
    v = admit(mixed).verdict
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.REFUSE_AND_INTERVIEW:
    print("gateable spine + vague remainder -> REFUSE-AND-INTERVIEW (do not admit an incomplete contract)")
    sys.exit(0)
print(f"ours={v} oracle=REFUSE-AND-INTERVIEW (ADMITting while assertions are still vague is the dangerous failure)")
sys.exit(1)
PYEOF
