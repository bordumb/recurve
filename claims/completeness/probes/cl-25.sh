#!/usr/bin/env bash
# CL-25: one raising probe body does not crash the whole aggregate coverage pass.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("mtrap", Path(fixture) / "broken_measured.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        covered_by = mod.covered_by
    else:
        from recurvelib.measured import covered_by

    def fa():
        return 1

    def fb():
        return 2

    def boom():
        raise ValueError("probe body errored")     # a RED/broken probe, mid-list
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    covered = covered_by([lambda: fa(), lambda: boom(), lambda: fb()], {"fa", "fb", "fc"})
except Exception as e:
    print(f"ours=covered_by crashed on a raising exercise ({type(e).__name__}) oracle=survives, returns {{fa,fb}}")
    sys.exit(1)

if covered == {"fa", "fb"}:
    print("a raising middle exercise is isolated: fa/fb coverage survives, boom contributes nothing")
    sys.exit(0)
print(f"ours={sorted(covered)} oracle=['fa','fb'] (the raising exercise must not lose the flanking coverage)")
sys.exit(1)
PYEOF
