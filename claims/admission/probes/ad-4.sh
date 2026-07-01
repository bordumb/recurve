#!/usr/bin/env bash
# AD-4: a goal whose every assertion is probe-able is ADMITted.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion, Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        admit = mod.admit
    else:
        from recurvelib.admission import admit

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    good = [A("1", True, True, True), A("2", True, True, True), A("3", True, True, True)]
    v = admit(good).verdict
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.ADMIT:
    print("every assertion probe-able -> ADMIT (a good contract is let through)")
    sys.exit(0)
print(f"ours={v} oracle=ADMIT (refusing a fully probe-able goal blocks real work)")
sys.exit(1)
PYEOF
