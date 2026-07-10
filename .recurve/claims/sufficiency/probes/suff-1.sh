#!/usr/bin/env bash
# SUFF-1: the pin call threads explicit free variables before hypotheses (docs/plans/autonomous_solver.md §1.2).
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
        goal_statement="goal a b",
        leaves=(Leaf(id="L1", statement="p1 a b", hypothesis_name="h1"),
                Leaf(id="L2", statement="p2 a b", hypothesis_name="h2")),
        assembly_proof="sorry",
        suite="demo",
        lean_module="Demo.Assembly",
        variables=("variable (a b : Nat)",),
        explicit_args=("a", "b"),
    )

    if fixture:
        spec = importlib.util.spec_from_file_location("suff1trap", Path(fixture) / "broken_check_source.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        src = mod.check_source(cut)
    else:
        from recurvelib.analysis.sufficiency import _check_source
        src = _check_source(cut)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

expected = "  demo_parent_assembly a b h1 h2"
if expected in src:
    print("pin call threads explicit_args before hypothesis names")
    sys.exit(0)
m = re.search(r"^\s*demo_parent_assembly.*$", src, re.MULTILINE)
print(f"ours={m.group(0).strip() if m else '(no call line found)'} oracle={expected.strip()}")
sys.exit(1)
PYEOF
