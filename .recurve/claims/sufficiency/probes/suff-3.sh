#!/usr/bin/env bash
# SUFF-3: the trap shares the real theorem's exact signature (docs/plans/autonomous_solver.md §1.2).
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
        assembly_proof="exact h1",
        suite="demo",
        lean_module="Demo.Assembly",
        variables=("variable (a b : Nat)",),
    )

    def signature(src):
        # Anchor on the EXACT theorem name at line-start — a bare `theorem \w+`
        # also matches prose like "-- this theorem derives the goal", which
        # would silently compare the wrong span.
        m = re.search(rf"^theorem {re.escape(cut.theorem_name)}\b(?:.|\n)*?:= by", src, re.MULTILINE)
        return m.group(0) if m else None

    if fixture:
        spec = importlib.util.spec_from_file_location("suff3trap", Path(fixture) / "broken_trap_source.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        real_sig = signature(mod.theorem_source(cut, cut.assembly_proof))
        trap_sig = signature(mod.trap_source(cut))
    else:
        from recurvelib.analysis.sufficiency import _theorem_source, _trap_source
        real_sig = signature(_theorem_source(cut, cut.assembly_proof))
        trap_sig = signature(_trap_source(cut))
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if real_sig is not None and real_sig == trap_sig:
    print("trap signature matches the real theorem's hypotheses + goal exactly")
    sys.exit(0)
print(f"ours=trap sig {trap_sig!r} oracle=real sig {real_sig!r} "
      f"(must be identical — only the proof body may differ)")
sys.exit(1)
PYEOF
