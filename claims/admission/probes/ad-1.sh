#!/usr/bin/env bash
# AD-1: probe-ability is the conjunction -- missing any one of falsifiable/counterexample/bounded disqualifies.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        probeable = mod.probeable
    else:
        def probeable(a):
            return a.probeable

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    cases = {"all": A("all", True, True, True),
             "nf": A("nf", False, True, True),    # missing oracle
             "nc": A("nc", True, False, True),    # missing counterexample
             "nb": A("nb", True, True, False)}    # unbounded
    res = {k: probeable(a) for k, a in cases.items()}
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if res == {"all": True, "nf": False, "nc": False, "nb": False}:
    print("probe-able only when all three criteria hold; missing any one disqualifies")
    sys.exit(0)
print(f"ours={res} oracle=only 'all' is probe-able (a missing oracle/counterexample/bound disqualifies)")
sys.exit(1)
PYEOF
