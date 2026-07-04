#!/usr/bin/env bash
# TK-21: `recurve demo` genuinely demonstrates a claim going RED then GREEN.
# run_demo(workdir) must return a trace whose steps show a REAL transition — a
# step with probe == "RED" FOLLOWED BY a step with probe == "GREEN" — proving a
# failing probe was actually fixed, not a hardcoded "GREEN". RED-first: a demo
# that only ever reports GREEN (never shows a failing probe) is RED here.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "strap", Path(fixture) / "broken_demo.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        run_demo = mod.run_demo
    else:
        from recurvelib.loop.demo import run_demo
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    with tempfile.TemporaryDirectory(prefix="recurve-tk21-") as tmp:
        trace = run_demo(Path(tmp))
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

steps = trace.get("steps") if isinstance(trace, dict) else None
if not isinstance(steps, list):
    print(f"ours=no-steps oracle=a-RED-step-then-a-GREEN-step")
    sys.exit(1)

probes = [s.get("probe") for s in steps if isinstance(s, dict)]
# A real transition: some RED step exists, and a GREEN step follows it.
transition = False
first_red = next((i for i, p in enumerate(probes) if p == "RED"), None)
if first_red is not None:
    transition = any(p == "GREEN" for p in probes[first_red + 1:])

ours = "->".join(str(p) for p in probes) or "empty"
if transition:
    print(f"ours=steps={ours} oracle=RED-then-GREEN "
          f"— the demo showed a failing probe going green")
    sys.exit(0)
print(f"ours=steps={ours} oracle=RED-then-GREEN "
      f"— no real transition: a probe seen RED must be followed by GREEN")
sys.exit(1)
PYEOF
