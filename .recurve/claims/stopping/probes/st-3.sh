#!/usr/bin/env bash
# ST-3: a converging approach is not abandoned (the controller continues while work shrinks).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Verdict, Progress
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        decide = mod.decide
    else:
        from recurvelib.controller import decide

    # open shrinks 5 -> 3 -> 1: real progress, not yet done.
    progressing = [
        Progress(open=5, regressed=0, broken=0, uncovered=0),
        Progress(open=3, regressed=0, broken=0, uncovered=0),
        Progress(open=1, regressed=0, broken=0, uncovered=0),
    ]
    v = decide(progressing)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if v == Verdict.CONTINUE:
    print("work shrinking 5->3->1 -> CONTINUE (a converging approach is not abandoned)")
    sys.exit(0)
print(f"ours={v} oracle=CONTINUE (reverting while progress is being made kills a plateau about to break)")
sys.exit(1)
PYEOF
