#!/usr/bin/env bash
# AD-8: an all-probe-able goal below min_invariants is still refused (perfect != enough).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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

    # one perfectly probe-able assertion: spine 1, total 1, below min_invariants 2.
    r = admit([Assertion("solo", "", True, True, True)])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if r.verdict == Verdict.REFUSE_NOT_GATEABLE:
    print("one perfect assertion (spine 1 < min 2) -> REFUSE-NOT-GATEABLE (too thin to be a contract)")
    sys.exit(0)
print(f"ours={r.verdict} oracle=REFUSE-NOT-GATEABLE ('perfectly probe-able' does not override 'too few invariants')")
sys.exit(1)
PYEOF
