#!/usr/bin/env bash
# SUFF-2: the check file never inlines the assembly theorem (docs/plans/autonomous_solver.md §1.2).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import re
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    from recurvelib.analysis.sufficiency import Cut, Leaf

    cut = Cut(
        parent_id="DEMO-PARENT",
        goal_statement="goal a",
        leaves=(Leaf(id="L1", statement="p1 a", hypothesis_name="h1"),),
        assembly_proof="sorry",
        suite="demo",
        lean_module="Demo.Assembly",
    )

    if fixture:
        spec = importlib.util.spec_from_file_location("suff2trap", Path(fixture) / "broken_check_source.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        src = mod.check_source(cut)
    else:
        from recurvelib.analysis.sufficiency import _check_source
        src = _check_source(cut)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

inlined = re.search(rf"\b(theorem|def)\s+{re.escape(cut.theorem_name)}\b", src)
if not inlined:
    print("check file contains only a statement pin — no inline theorem/def")
    sys.exit(0)
print(f"ours=check file declares '{inlined.group(0)}' "
      f"oracle=no theorem/def declaration of {cut.theorem_name} in the check file")
sys.exit(1)
PYEOF
