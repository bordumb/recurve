#!/usr/bin/env bash
# AD-6: a probe-able spine below min_invariants -> REFUSE-NOT-GATEABLE (too thin to be a contract).
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

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    # only 1 assertion is probe-able -> spine 1 < min_invariants 2.
    thin = [A("1", True, True, True), A("2", False, True, True), A("3", True, False, True), A("4", True, True, False)]
    v = admit(thin).verdict
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.REFUSE_NOT_GATEABLE:
    print("spine of 1 (< min 2) -> REFUSE-NOT-GATEABLE (too few invariants to gate honestly)")
    sys.exit(0)
print(f"ours={v} oracle=REFUSE-NOT-GATEABLE (gating a one-invariant goal forces a brittle proxy)")
sys.exit(1)
PYEOF
