#!/usr/bin/env bash
# CL-26: a probe body that calls sys.exit() (SystemExit) is isolated, not fatal to the coverage pass.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("mtrap", Path(fixture) / "broken_measured.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        covered_by = mod.covered_by
    else:
        from recurvelib.analysis.measured import covered_by

    def fa():
        return 1

    def fb():
        return 2

    def exiter():
        sys.exit(0)                        # a skip-guarded probe body
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    covered = covered_by([lambda: fa(), lambda: exiter(), lambda: fb()], {"fa", "fb"})
except BaseException as e:                 # a SystemExit escaping covered_by is the failure
    print(f"ours=covered_by let {type(e).__name__} escape oracle=isolated, returns {{fa, fb}}")
    sys.exit(1)

if covered == {"fa", "fb"}:
    print("a sys.exit() probe body is isolated: fa/fb coverage survives the whole pass")
    sys.exit(0)
print(f"ours={sorted(covered)} oracle=['fa','fb']")
sys.exit(1)
PYEOF
