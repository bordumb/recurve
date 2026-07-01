#!/usr/bin/env bash
# RT-9: a diff path that escapes the target tree via '..' or an absolute path is rejected (A4).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        within_boundary = mod.within_boundary
    else:
        from recurvelib.runtime import within_boundary

    escape = within_boundary(["repo/../secret.py"], "repo/", ["repo/claims/"])   # climbs out via ..
    absolute = within_boundary(["/etc/passwd"], "repo/", ["repo/claims/"])       # absolute path
    clean = within_boundary(["repo/src/foo.py"], "repo/", ["repo/claims/"])      # legitimate, still accepted
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if escape is False and absolute is False and clean is True:
    print("'..' and absolute paths are rejected; a normal target-tree path still passes")
    sys.exit(0)
print(f"ours=(escape={escape}, absolute={absolute}, clean={clean}) oracle=(False, False, True) "
      f"(startswith without normalization lets repo/../secret.py escape the target tree)")
sys.exit(1)
PYEOF
