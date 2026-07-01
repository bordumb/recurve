#!/usr/bin/env bash
# TK-22: `recurve init <path>` infers the mode from what <path> is, and never
# silently misreads a spec. infer_init_mode(path) must return "from-prd" for a
# FILE, "from-repo" for a directory that is a git repo (or holds docs), and
# "blank" for an empty directory. RED-first: an infer that returns "blank" for
# a spec FILE (silently ignoring a spec — the worst inference) is RED here.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "strap", Path(fixture) / "broken_infer.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        infer_init_mode = mod.infer_init_mode
    else:
        from recurvelib.init import infer_init_mode
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    with tempfile.TemporaryDirectory(prefix="recurve-tk22-") as tmp:
        tmp = Path(tmp)
        # A spec FILE must infer from-prd (claimify a spec).
        spec_file = tmp / "spec.md"
        spec_file.write_text("# spec\nThe API must reject an expired token.\n")
        prd = infer_init_mode(spec_file)[0]
        # A directory that is a git repo must infer from-repo (mine promises).
        repo_dir = tmp / "repo"
        (repo_dir / ".git").mkdir(parents=True)
        repo = infer_init_mode(repo_dir)[0]
        # An empty directory must infer blank (a fresh scaffold).
        empty_dir = tmp / "empty"
        empty_dir.mkdir()
        blank = infer_init_mode(empty_dir)[0]
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

green = prd == "from-prd" and repo == "from-repo" and blank == "blank"
if green:
    print(f"ours=file={prd},gitdir={repo},empty={blank} "
          f"oracle=file=from-prd,gitdir=from-repo,empty=blank "
          f"— init infers the mode and never silently ignores a spec")
    sys.exit(0)
print(f"ours=file={prd},gitdir={repo},empty={blank} "
      f"oracle=file=from-prd,gitdir=from-repo,empty=blank")
sys.exit(1)
PYEOF
