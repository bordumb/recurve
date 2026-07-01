#!/usr/bin/env bash
# AD-14: only an ADMITted goal proceeds to synthesis; a REFUSE verdict never does (no bypass).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion, admit
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_admission.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        admitted = mod.admitted
    else:
        from recurvelib.admission import admitted

    def A(i, f, c, b):
        return Assertion(i, "", f, c, b)

    admit_rep = admit([A("1", True, True, True), A("2", True, True, True), A("3", True, True, True)])
    interview_rep = admit([A("1", True, True, True), A("2", True, True, True), A("3", False, True, True)])
    notgate_rep = admit([A("1", True, True, True), A("2", False, True, True), A("3", False, True, True)])
    results = (admitted(admit_rep), admitted(interview_rep), admitted(notgate_rep))
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if results == (True, False, False):
    print("only ADMIT proceeds: (admit=True, interview=False, not-gateable=False)")
    sys.exit(0)
print(f"ours={results} oracle=(True, False, False) (letting a REFUSE goal synthesize bypasses the whole gate)")
sys.exit(1)
PYEOF
