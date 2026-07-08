#!/usr/bin/env bash
# SOLV-5: budget exhaustion halts an unbounded recursion (docs/plans/autonomous_solver.md §2.3).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
import textwrap
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

from recurvelib.analysis.sufficiency import Cut, Leaf
from recurvelib.core.config import load


def make_config(tmpdir):
    toml_path = Path(tmpdir) / "recurve.toml"
    toml_path.write_text(textwrap.dedent("""\
        [project]
        name = "solver-test"
        [target]
        tree = "."
        [reads.none]
        method = "none"
        [suites.demo]
        dir = "demo"
        """))
    suite_dir = Path(tmpdir) / "demo"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "gaps.yaml").write_text("[]\n")
    return load(toml_path)


class FakeResult:
    ok = True
    detail = "fake GREEN (never actually promotes — leaves stay open on purpose)"


def fake_sufficiency_check(cut, config, today, timeout_s=300):
    # Deliberately never writes to the ledger: this test's chain must NEVER close, so
    # budget exhaustion (not a lucky early close) is what has to stop the recursion.
    return FakeResult()


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)

        def cut_proposer(gap_id, ctx):
            # An "infinite" chain: BUDGET-N always decomposes into BUDGET-(N+1). Without a
            # budget this would recurse forever; capped at 50 as a test-level safety net
            # independent of solver's own budget (well under Python's default recursion
            # limit, so a broken budget check fails the assertion below with a clean,
            # readable count rather than crashing on RecursionError).
            n = int(gap_id.split("-")[1])
            if n > 50:
                return None
            child = f"BUDGET-{n + 1}"
            return Cut(parent_id=gap_id, goal_statement="g",
                       leaves=(Leaf(id=child, statement="p", hypothesis_name="h"),),
                       assembly_proof="exact trivial", suite="demo",
                       lean_module=f"Demo.{gap_id.replace('-', '')}")

        if fixture:
            spec = importlib.util.spec_from_file_location("solv5trap", Path(fixture) / "broken_budget.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            Budget = mod.Budget
        else:
            from recurvelib.loop.solver import Budget

        from recurvelib.loop.solver import SolveContext, solve
        ctx = SolveContext(config=config, today="2026-01-01",
                           close_attempt=lambda gid, c: None, cut_proposer=cut_proposer,
                           sufficiency_check=fake_sufficiency_check,
                           budget=Budget(max_moves=5))
        result = solve("BUDGET-0", ctx)

        visited = len(set(result.frontier))
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

# Exactly 5 moves spent visits BUDGET-0..BUDGET-5 (the 6th call is turned away at the
# budget check before it does any work) -- all 6 end up in frontier (5 "no move applies"
# ancestors whose sub-tree never closed, plus BUDGET-5 itself "budget exhausted").
if visited == 6 and "BUDGET-5" in result.frontier:
    print(f"budget correctly capped the recursion at {visited} nodes, not an unbounded chain")
    sys.exit(0)
print(f"ours=visited={visited} frontier={result.frontier} oracle=visited=6, BUDGET-5 present")
sys.exit(1)
PYEOF
