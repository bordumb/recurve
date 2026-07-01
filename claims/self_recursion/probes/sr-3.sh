#!/usr/bin/env bash
# SR-3: recurve run materializes the shipped template FULLY INTERPOLATED before it
# runs — no {{...}} placeholder survives. The raw template's ${RECURVE_BIN:-{{PROG}}}
# mis-parses under bash (the }} leaks into PROG), so it must be interpolated, not
# run raw. RED-first: a materialize that returns the template with placeholders
# intact is RED.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.config import load
    from recurvelib.run import resolve_workflow
    cfg = load(Path(root) / "recurve.toml")
    script = resolve_workflow(cfg, False)
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "mtrap", Path(fixture) / "broken_run.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        materialize_workflow = mod.materialize_workflow
    else:
        from recurvelib.run import materialize_workflow
    text = Path(materialize_workflow(cfg, script)).read_text()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if "{{" not in text and "PROG=" in text:
    print("materialized workflow is fully interpolated — no placeholder survives; runnable under bash")
    sys.exit(0)
leak = next((ln.strip() for ln in text.splitlines() if "{{" in ln), "")
print(f"ours=placeholder survives: {leak[:60]!r} oracle=no placeholders survive in the materialized workflow")
sys.exit(1)
PYEOF
