#!/usr/bin/env bash
# AP-6: GitWorld.restore fails safe on an unknown sha (RestoreError), never a raw CalledProcessError.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress
    from recurvelib.adapters import RestoreError
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        for c in (["init", "-q"], ["config", "user.email", "r@r"], ["config", "user.name", "r"]):
            subprocess.run(["git", "-C", d, *c], check=True)
        (Path(d) / "a.txt").write_text("x")
        w = GitWorld(d, [], lambda x: Progress(0, 0, 0, 0))
        w.checkpoint()
        try:
            w.restore("deadbeef" * 5)               # not a real sha
            result = "returned"
        except RestoreError:
            result = "RestoreError"
        except Exception as e:
            result = f"raw {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "RestoreError":
    print("restore on an unknown sha -> RestoreError (the revert path fails in a catchable way)")
    sys.exit(0)
print(f"ours={result} oracle=RestoreError (a raw CalledProcessError turns the safety revert into a crash)")
sys.exit(1)
PYEOF
