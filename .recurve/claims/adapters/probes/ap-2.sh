#!/usr/bin/env bash
# AP-2: GitWorld checkpoint/restore round-trips on a real git tree.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Progress
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.loop.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "r@r"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "r"], check=True)
        r = Path(d)
        (r / "t.txt").write_text("ORIG")
        w = GitWorld(r, [], lambda x: Progress(0, 0, 0, 0))
        snap = w.checkpoint()
        (r / "t.txt").write_text("MUTATED")
        w.restore(snap)
        result = (r / "t.txt").read_text()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "ORIG":
    print("checkpoint then restore rolls the working tree back to the snapshot")
    sys.exit(0)
print(f"ours=t.txt after restore={result!r} oracle='ORIG' (a no-op restore leaves the damage in place — revert is a lie)")
sys.exit(1)
PYEOF
