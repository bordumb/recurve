#!/usr/bin/env bash
# AP-11: checkpoint works on a repo with no configured git identity (it supplies one).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
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
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
        (Path(d) / "a.txt").write_text("x")
        # isolate identity so the trap (no -c) has nothing to fall back on
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            os.environ.pop(k, None)
        os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
        os.environ["GIT_CONFIG_SYSTEM"] = "/dev/null"
        w = GitWorld(d, [], lambda x: Progress(0, 0, 0, 0))
        try:
            sha = w.checkpoint()
            result = "committed" if sha else "empty"
        except Exception as e:
            result = f"raised {type(e).__name__}"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result == "committed":
    print("checkpoint succeeds on a repo with no configured user (identity supplied via -c)")
    sys.exit(0)
print(f"ours={result} oracle=committed (relying on ambient git config crashes the loop's first action)")
sys.exit(1)
PYEOF
