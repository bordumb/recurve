#!/usr/bin/env bash
# CL-10: declared coverage aggregates as the union of every claim's `covers` field.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("cmptrap", Path(fixture) / "broken_completeness.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        covered_ids = mod.covered_ids
    else:
        from recurvelib.analysis.completeness import covered_ids

    claims = [{"covers": ["a", "b"]}, {"covers": ["c"]}, {"id": "x"}]  # last claim covers nothing
    ids = covered_ids(claims)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"a", "b", "c"}:
    print("covered ids are the union of every claim's covers: {a, b, c}")
    sys.exit(0)
print(f"ours={sorted(ids)} oracle=['a','b','c'] (a claim that covers nothing contributes nothing)")
sys.exit(1)
PYEOF
