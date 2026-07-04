#!/usr/bin/env bash
# RT-4: the write boundary keeps the actor off the referee surface (A4).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        within_boundary = mod.within_boundary
    else:
        from recurvelib.loop.runtime import within_boundary

    target, referee = "repo/", ["repo/claims/"]
    clean = within_boundary(["repo/src/foo.py"], target, referee)            # target tree only
    referee_edit = within_boundary(["repo/claims/x/probe.sh"], target, referee)  # touches the referee surface
    outside = within_boundary(["other/foo.py"], target, referee)             # outside the target entirely
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if clean is True and referee_edit is False and outside is False:
    print("target-only diff accepted; a probe-editing diff and an outside diff both rejected")
    sys.exit(0)
print(f"ours=(clean={clean}, referee={referee_edit}, outside={outside}) oracle=(True, False, False) "
      f"(accepting a referee-surface edit lets the actor weaken its own test)")
sys.exit(1)
PYEOF
