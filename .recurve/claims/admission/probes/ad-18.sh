#!/usr/bin/env bash
# AD-18: admitted is true only for the ADMIT verdict (by identity); an unknown/None verdict fails CLOSED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.analysis.admission import AdmissionReport
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        admitted = mod.admitted
    else:
        from recurvelib.analysis.admission import admitted

    # a malformed / future report whose verdict is neither ADMIT nor a known REFUSE.
    unknown = AdmissionReport(verdict=None, probeable=0, total=0, gateability=0.0, worklist=(), min_invariants=2)
    result = admitted(unknown)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result is False:
    print("an unknown/None verdict -> admitted False (the gate fails closed, never open)")
    sys.exit(0)
print(f"ours=admitted {result} oracle=False ('not a REFUSE' fails open: any unknown verdict reaches synthesis)")
sys.exit(1)
PYEOF
