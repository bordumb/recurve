#!/usr/bin/env bash
# AP-4: the full loop, on a real git repo with a command actor, burns a RED file to GREEN and stops.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.controller import Progress, Verdict
    from recurvelib.runtime import run
    from recurvelib.admission import Assertion, admit
    from recurvelib.adapters import CommandActor
    if fixture:
        spec = importlib.util.spec_from_file_location("atrap", Path(fixture) / "broken_adapters.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitWorld = mod.GitWorld
    else:
        from recurvelib.adapters import GitWorld

    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "r@r"], check=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "r"], check=True)
        r = Path(d)
        (r / "target.txt").write_text("RED")
        (r / "claims").mkdir()
        (r / "claims" / "probe.sh").write_text("guard")

        def gate_fn(x):
            red = 1 if "RED" in (Path(x) / "target.txt").read_text() else 0
            return Progress(open=red, regressed=0, broken=0, uncovered=0)

        w = GitWorld(r, ["claims/"], gate_fn)
        actor = CommandActor(["python3", "-c",
                              "import json,sys; json.load(sys.stdin); print(json.dumps({'target.txt':'GREEN'}))"])
        rep = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True)])
        verdict, _ = run(w, actor, rep, "contract")
        fixed = (r / "target.txt").read_text() == "GREEN"
        referee_ok = (r / "claims" / "probe.sh").read_text() == "guard"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if verdict is Verdict.STOP_SUCCESS and fixed and referee_ok:
    print("live loop on a real repo: RED -> GREEN on disk, STOP-SUCCESS, referee untouched")
    sys.exit(0)
print(f"ours=(verdict={verdict}, fixed={fixed}, referee_ok={referee_ok}) oracle=(STOP_SUCCESS, True, True) "
      f"(a loop that never applies the patch can't fix the tree)")
sys.exit(1)
PYEOF
