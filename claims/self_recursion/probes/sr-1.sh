#!/usr/bin/env bash
# SR-1: `recurve run` resolves a runnable burndown workflow on the recurve repo
# ITSELF (the self-host layout — recurve.toml at root, no stamped .recurve/
# workflows/), instead of erroring "no workflow — run init first". This is the
# plumbing that lets the loop run on its own repo. RED-first: a resolver that
# only finds a stamped .recurve/workflows/ workflow is RED on the self-host repo.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.config import load
    cfg = load(Path(root) / "recurve.toml")
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_run.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        resolve_workflow = mod.resolve_workflow
    else:
        from recurvelib.run import resolve_workflow
    wf = resolve_workflow(cfg, False)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if wf is not None and Path(wf).exists():
    print(f"the loop is runnable on its own repo: recurve run resolves {wf}")
    sys.exit(0)
print(f"ours={wf!r} (exists={bool(wf is not None and Path(wf).exists())}) "
      f"oracle=an existing, runnable burndown workflow on the self-host repo")
sys.exit(1)
PYEOF
