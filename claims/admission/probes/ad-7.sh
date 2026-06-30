#!/usr/bin/env bash
# AD-7: an empty goal is never gateable (zero invariants is not a perfect contract).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Verdict
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        admit = mod.admit
    else:
        from recurvelib.admission import admit

    r = admit([])
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if r.verdict == Verdict.REFUSE_NOT_GATEABLE and r.gateability == 0.0:
    print("empty goal -> REFUSE-NOT-GATEABLE, gateability 0.0 (no assertion is not every assertion)")
    sys.exit(0)
print(f"ours=({r.verdict}, g={r.gateability}) oracle=(REFUSE-NOT-GATEABLE, 0.0) (admitting an empty goal lets pure garbage in)")
sys.exit(1)
PYEOF
