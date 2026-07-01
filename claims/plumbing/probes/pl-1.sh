#!/usr/bin/env bash
# PL-1: `recurve decide` surfaces the stopping controller — its logic
# (recurvelib.decide_cli.verdict_for) mirrors controller.decide exactly, so the
# loop can ask recurve for a verdict from a measured progress vector. RED-first:
# until the surface exists the probe is RED; a surface whose verdict disagrees
# with controller.decide is RED.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import decide, Progress  # the oracle
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "dtrap", Path(fixture) / "broken_decide.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        verdict_for = mod.verdict_for
    else:
        from recurvelib.decide_cli import verdict_for
except ImportError:
    print("ours=no `recurve decide` surface yet oracle=verdict_for mirrors controller.decide")
    sys.exit(1)  # RED-first: the surface does not exist

cases = [(0, 0, 0, 0, False), (2, 0, 0, 0, False), (0, 0, 1, 0, False), (0, 0, 0, 3, False),
         (0, 0, 0, 0, True)]  # green BUT divergent -> must be CONTINUE, never STOP-SUCCESS
for c in cases:
    want = decide([Progress(*c)]).value
    try:
        got = verdict_for(*c)
    except Exception as e:
        print(f"ours=verdict_for raised {type(e).__name__} oracle={want!r} for {c}")
        sys.exit(1)
    if got != want:
        print(f"ours={got!r} oracle={want!r} for vector {c} — the verb must mirror controller.decide")
        sys.exit(1)

print("recurve decide surfaces the controller faithfully: verdict_for mirrors controller.decide")
sys.exit(0)
PYEOF
