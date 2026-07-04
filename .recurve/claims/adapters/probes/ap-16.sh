#!/usr/bin/env bash
# AP-16: a patch key under a symlinked prefix pointing out of the tree is refused, nothing written outside.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Progress
    from recurvelib.loop.adapters import BoundaryViolation
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.loop.adapters import GitWorld

    with tempfile.TemporaryDirectory() as inside, tempfile.TemporaryDirectory() as outside:
        r = Path(inside)
        (r / "link").symlink_to(outside)             # a symlink inside the tree pointing OUT
        w = GitWorld(r, [], lambda x: Progress(0, 0, 0, 0))
        refused = False
        try:
            w.apply({"link/pwned": "ESCAPED"})
        except BoundaryViolation:
            refused = True
        except Exception:
            refused = False
        wrote_outside = (Path(outside) / "pwned").exists()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if refused and not wrote_outside:
    print("a symlinked prefix escape is refused (BoundaryViolation); nothing written outside the tree")
    sys.exit(0)
print(f"ours=(refused={refused}, wrote_outside={wrote_outside}) oracle=(True, False) "
      f"(a string-only boundary follows the symlink and writes out of the tree)")
sys.exit(1)
PYEOF
