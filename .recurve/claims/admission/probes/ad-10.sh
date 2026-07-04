#!/usr/bin/env bash
# AD-10: each worklist gap names the SPECIFIC failed criterion (content, not just count).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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
        worklist = mod.worklist
    else:
        from recurvelib.admission import worklist

    # one assertion missing only the oracle; one missing only the bound.
    no_oracle = worklist([Assertion("o", "", False, True, True)])[0][1][0]
    unbounded = worklist([Assertion("u", "", True, True, False)])[0][1][0]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if no_oracle == "no observable pass/fail (no oracle)" and unbounded == "unbounded scope (no enumerable surface)":
    print("each gap names the actual failed criterion (oracle / bound), not a constant placeholder")
    sys.exit(0)
print(f"ours=(oracle-case='{no_oracle}', bound-case='{unbounded}') oracle=the matching criterion strings "
      f"(mislabeled gaps send the interview to fix the wrong thing)")
sys.exit(1)
PYEOF
