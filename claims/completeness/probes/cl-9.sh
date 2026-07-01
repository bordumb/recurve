#!/usr/bin/env bash
# CL-9: extraction is deterministic — the same source twice yields the identical (id, location) sequence.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
SRC = (
    "def b():\n    pass\ndef a():\n    pass\n"
    "class C:\n    def z(self):\n        pass\n    def y(self):\n        pass\n"
)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("strap", Path(fixture) / "broken_surface.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        extract = mod.extract
    else:
        from recurvelib.surface import PythonAdapter
        extract = PythonAdapter().extract
    seq1 = [(p.id, p.location) for p in extract(SRC, "t.py")]
    seq2 = [(p.id, p.location) for p in extract(SRC, "t.py")]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if seq1 == seq2 and seq1 == sorted(seq1):
    print(f"deterministic: identical sorted sequence across two extractions ({len(seq1)} points)")
    sys.exit(0)
print(f"ours=seq1 {seq1} vs seq2 {seq2} oracle=identical, sorted (a nondeterministic surface is unusable as a baseline)")
sys.exit(1)
PYEOF
