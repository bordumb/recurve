#!/usr/bin/env bash
# SOLV-4: a node with no applicable move becomes a frontier point (docs/plans/autonomous_solver.md §2.3).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
import textwrap
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

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


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)

        def close_attempt(gap_id, ctx):
            return None  # no known direct proof

        def cut_proposer(gap_id, ctx):
            return None  # no known decomposition either

        if fixture:
            spec = importlib.util.spec_from_file_location("solv4trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01", close_attempt=close_attempt,
                           cut_proposer=cut_proposer)
        result = run("STUCK", ctx)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result.frontier == ("STUCK",) and not result.closed:
    print("a node with no applicable move is surfaced in frontier, not silently dropped")
    sys.exit(0)
print(f"ours=closed={result.closed} frontier={result.frontier} "
      f"oracle=closed=() frontier=('STUCK',)")
sys.exit(1)
PYEOF
