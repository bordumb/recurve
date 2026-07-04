#!/usr/bin/env bash
# AP-18: checkpoint surfaces a git failure as a typed CheckpointError (symmetric with restore's RestoreError).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress
    from recurvelib.adapters import CheckpointError
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
        (Path(d) / "a.txt").write_text("x")
        w = GitWorld(d, [], lambda x: Progress(0, 0, 0, 0))
        os.environ["PATH"] = "/nonexistent"      # hide git on the snapshot path
        try:
            w.checkpoint()
            result = "returned"
        except CheckpointError:
            result = "CheckpointError"
        except Exception as e:
            result = f"raw {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "CheckpointError":
    print("git missing on the snapshot path -> CheckpointError (typed), symmetric with RestoreError")
    sys.exit(0)
print(f"ours={result} oracle=CheckpointError (an unwrapped checkpoint leaks a raw GitError)")
sys.exit(1)
PYEOF
