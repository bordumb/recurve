#!/usr/bin/env bash
# SUFF-5: children_of / parents_of invert each other over covers_claim (docs/plans/autonomous_solver.md §1.3).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from collections import namedtuple
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

SimpleGap = namedtuple("SimpleGap", ["id", "covers_claim"])
gaps = [
    SimpleGap("PARENT-A", ()),
    SimpleGap("LEAF-A1", ("PARENT-A",)),
    SimpleGap("PARENT-B", ()),
    SimpleGap("LEAF-B1", ("PARENT-B",)),
]

try:
    if fixture:
        spec = importlib.util.spec_from_file_location("suff5trap", Path(fixture) / "broken_dag.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        children_of = lambda pid: mod.children_of(gaps, pid)
        parents_of = lambda cid: mod.parents_of(gaps, cid)
    else:
        from recurvelib.core.model import Ledger, SuiteLedger
        ledger = Ledger(suites=(SuiteLedger(suite="demo", suite_dir=Path("/tmp"), gaps=tuple(gaps)),))
        children_of = ledger.children_of
        parents_of = ledger.parents_of

    kids_a = sorted(g.id for g in children_of("PARENT-A"))
    kids_b = sorted(g.id for g in children_of("PARENT-B"))
    parents_leaf_a1 = sorted(g.id for g in parents_of("LEAF-A1"))
    parents_root = sorted(g.id for g in parents_of("PARENT-A"))
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

ok = (kids_a == ["LEAF-A1"] and kids_b == ["LEAF-B1"]
      and parents_leaf_a1 == ["PARENT-A"] and parents_root == [])
if ok:
    print("children_of/parents_of correctly select by exact parent id")
    sys.exit(0)
print(f"ours=children_of(PARENT-A)={kids_a} children_of(PARENT-B)={kids_b} "
      f"parents_of(LEAF-A1)={parents_leaf_a1} parents_of(PARENT-A)={parents_root} "
      f"oracle=['LEAF-A1'] ['LEAF-B1'] ['PARENT-A'] []")
sys.exit(1)
PYEOF
