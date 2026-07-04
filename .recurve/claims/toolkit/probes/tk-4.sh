#!/usr/bin/env bash
# TK-4: a second loop on one tree is refused while the first holds the lock.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
if fixture:
    spec = importlib.util.spec_from_file_location(
        "lockmod", Path(fixture) / "permissive_lock.py")
    lockmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lockmod)
else:
    from recurvelib.loop import lock as lockmod

with tempfile.TemporaryDirectory() as td:
    first = lockmod.TreeLock(Path(td))
    first.acquire()
    try:
        lockmod.TreeLock(Path(td)).acquire()
        print("ours=second loop admitted oracle=refusal (two loops corrupt one tree)")
        sys.exit(1)
    except lockmod.LockHeld:
        print("second loop refused while the first holds the tree")
        sys.exit(0)
    finally:
        first.release()
PYEOF
