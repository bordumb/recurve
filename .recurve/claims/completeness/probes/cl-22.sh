#!/usr/bin/env bash
# CL-22: a bare-string `covers` is one id, never exploded into character-ids.
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
        from recurvelib.completeness import covered_ids

    ids = covered_ids([{"covers": "verify_chain"}])  # a single id written as a bare string
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if ids == {"verify_chain"}:
    print("a string covers is one id: {verify_chain} (not exploded into characters)")
    sys.exit(0)
print(f"ours={sorted(ids)} oracle={{'verify_chain'}} (a char-exploded covers loses the intended coverage)")
sys.exit(1)
PYEOF
