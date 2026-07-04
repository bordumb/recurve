#!/usr/bin/env bash
# AP-12: a missing git binary surfaces as a typed error from restore, not a raw FileNotFoundError.
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
    from recurvelib.adapters import RestoreError
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        for c in (["init", "-q"], ["config", "user.email", "r@r"], ["config", "user.name", "r"]):
            subprocess.run(["git", "-C", d, *c], check=True)
        (Path(d) / "a.txt").write_text("x")
        w = GitWorld(d, [], lambda x: Progress(0, 0, 0, 0))
        w.checkpoint()                       # make a HEAD to restore, while git is still available
        os.environ["PATH"] = "/nonexistent"  # now hide the git binary
        try:
            w.restore("HEAD")
            result = "returned"
        except RestoreError:
            result = "RestoreError"
        except Exception as e:
            result = f"raw {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "RestoreError":
    print("git missing on the revert path -> RestoreError (typed), not a raw FileNotFoundError")
    sys.exit(0)
print(f"ours={result} oracle=RestoreError (catching only CalledProcessError leaks a raw error on git-missing)")
sys.exit(1)
PYEOF
