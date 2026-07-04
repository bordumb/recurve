#!/usr/bin/env bash
# SR-4: a live cycle on the self-host repo is handed a REAL, interpolated per-cycle
# contract — recurve run materializes RUN.md alongside the workflow and points the
# cycle prompt at it, instead of a dangling .recurve/RUN.md that does not exist on
# the self-host layout. RED-first: a materialize that leaves the contract dangling
# (no interpolated RUN.md the workflow points at) is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.config import find_config, load
    from recurvelib.run import resolve_workflow
    cfg = load(find_config(Path(root)))
    script = resolve_workflow(cfg, False)
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "mtrap", Path(fixture) / "broken_run.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        materialize_workflow = mod.materialize_workflow
    else:
        from recurvelib.run import materialize_workflow
    wf = Path(materialize_workflow(cfg, script))
    wf_text = wf.read_text()
    contract = wf.parent / "RUN.md"
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

ok = (contract.exists()
      and "{{" not in contract.read_text()
      and str(contract) in wf_text)
if ok:
    print(f"the cycle is handed a real interpolated contract: {contract}")
    sys.exit(0)
print(f"ours=(contract_exists={contract.exists()}, referenced={str(contract) in wf_text}) "
      f"oracle=an interpolated RUN.md the workflow points the cycle at")
sys.exit(1)
PYEOF
