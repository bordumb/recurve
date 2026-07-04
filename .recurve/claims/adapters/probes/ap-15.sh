#!/usr/bin/env bash
# AP-15: a failed apply rolls the whole tree back even when a rollback step would itself fail (no mixed tree).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "top").write_text("PRIOR")     # a pre-existing file, written first
        (r / "sub").mkdir()                 # a pre-existing DIR — the second key can't be written over it
        w = GitWorld(r, [], lambda x: Progress(0, 0, 0, 0))
        try:
            w.apply({"top": "MUTATED", "sub": "text-over-a-dir"})
        except Exception:
            pass
        top_after = (r / "top").read_text()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if top_after == "PRIOR":
    print("a failed apply restores 'top' fully — rollback completes despite the dir-collision on 'sub'")
    sys.exit(0)
print(f"ours=top after failed apply={top_after!r} oracle='PRIOR' (an unguarded rollback leaves a mixed tree)")
sys.exit(1)
PYEOF
