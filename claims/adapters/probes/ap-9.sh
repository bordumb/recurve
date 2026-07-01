#!/usr/bin/env bash
# AP-9: apply rolls back a created directory, not just created files (all-or-nothing includes dirs).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
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
        (r / "collide").write_text("i am a file")     # so mkdir('collide') fails AFTER 'fresh/' is created
        w = GitWorld(r, [], lambda x: Progress(0, 0, 0, 0))
        try:
            w.apply({"fresh/a": "x", "collide/b": "y"})
        except Exception:
            pass
        orphan = (r / "fresh").exists()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if not orphan:
    print("a failed apply removes the directory it created: no orphan 'fresh/' after rollback")
    sys.exit(0)
print("ours=orphan dir 'fresh/' left on disk oracle=removed (a 'rolled back' apply must leave no new dirs)")
sys.exit(1)
PYEOF
