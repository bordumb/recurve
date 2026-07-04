#!/usr/bin/env bash
# AP-1: GitWorld.apply enforces the write boundary on a real tree (referee patch refused, clean patch written).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress
    from recurvelib.adapters import BoundaryViolation
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "claims").mkdir()
        (r / "claims" / "probe.sh").write_text("guard")
        w = GitWorld(r, ["claims/"], lambda x: Progress(0, 0, 0, 0))

        refused = False
        try:
            w.apply({"claims/probe.sh": "HACKED"})     # referee surface — must be refused
        except BoundaryViolation:
            refused = True
        referee_intact = (r / "claims" / "probe.sh").read_text() == "guard"

        w.apply({"src/foo.py": "ok"})                  # target tree — must be written
        clean_written = (r / "src" / "foo.py").read_text() == "ok"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if refused and referee_intact and clean_written:
    print("apply refuses a referee-surface patch (nothing written) and writes a target-tree patch")
    sys.exit(0)
print(f"ours=(refused={refused}, referee_intact={referee_intact}, clean_written={clean_written}) "
      f"oracle=(True, True, True) (an unguarded apply lets the actor edit its own probes on disk)")
sys.exit(1)
PYEOF
