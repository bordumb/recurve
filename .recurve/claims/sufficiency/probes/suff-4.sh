#!/usr/bin/env bash
# SUFF-4: a claim cannot name itself as its own decomposition parent (docs/plans/autonomous_solver.md §1.3).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

raw = {
    "id": "SELF-1",
    "status": "permanent",
    "title": "t",
    "class": "missing-surface",
    "severity": "feature",
    "smallest_fix": "n/a",
    "covers_claim": ["SELF-1"],
}

try:
    if fixture:
        spec = importlib.util.spec_from_file_location("suff4trap", Path(fixture) / "broken_parse.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        parse_covers_claim = mod.parse_covers_claim
    else:
        def parse_covers_claim(r):
            from recurvelib.core.model import Gap
            Gap.parse(r, "demo", Path("/tmp"), Path("/tmp/gaps.yaml"), ("none",), "none")

    raised = False
    try:
        parse_covers_claim(raw)
    except Exception:
        raised = True
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if raised:
    print("covers_claim: [<own id>] is rejected at parse time")
    sys.exit(0)
print("ours=no error raised oracle=GapParseError (a claim cannot be its own decomposition parent)")
sys.exit(1)
PYEOF
