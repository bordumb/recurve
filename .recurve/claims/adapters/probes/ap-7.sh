#!/usr/bin/env bash
# AP-7: GitWorld.apply is all-or-nothing against write failures, not just boundary rejections.
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
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.loop.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        w = GitWorld(r, [], lambda x: Progress(0, 0, 0, 0))
        # "a" (a file) and "a/b" (needs "a" as a dir) collide -> the second write fails mid-patch.
        try:
            w.apply({"a": "FIRST", "a/b": "SECOND"})
            raised = False
        except Exception:
            raised = True
        left_on_disk = (r / "a").exists()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if raised and not left_on_disk:
    print("a failed multi-key patch is rolled back: 'a' is absent after the raise (no partial mutation)")
    sys.exit(0)
print(f"ours=(raised={raised}, 'a' left_on_disk={left_on_disk}) oracle=(True, False) "
      f"(a non-atomic apply leaves the tree in a state that is neither old nor proposed)")
sys.exit(1)
PYEOF
