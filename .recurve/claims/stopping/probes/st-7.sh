#!/usr/bin/env bash
# ST-7: a cycle that is not truly green (broken/regressed/divergent) never stops with success.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Verdict, Progress
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        decide = mod.decide
    else:
        from recurvelib.loop.controller import decide

    # each cycle has zero open + uncovered, but is not truly done — none may stop with success.
    cases = {
        "broken": Progress(open=0, regressed=0, broken=3, uncovered=0),
        "regressed": Progress(open=0, regressed=4, broken=0, uncovered=0),
        "divergent": Progress(open=0, regressed=0, broken=0, uncovered=0, divergent=True),
    }
    leaked = [name for name, p in cases.items() if decide([p]) == Verdict.STOP_SUCCESS]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if not leaked:
    print("broken/regressed/divergent cycles all refuse STOP-SUCCESS (no false 'done')")
    sys.exit(0)
print(f"ours=STOP-SUCCESS on {leaked} oracle=never (you cannot declare done on unmeasured/regressed/diverged work)")
sys.exit(1)
PYEOF
