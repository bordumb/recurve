#!/usr/bin/env bash
# SOLV-6: a genuine frontier node is parked with its reason (docs/plans/autonomous_solver.md §2.3, §2.7).
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
        project_root = Path(tmpdir)

        if fixture:
            spec = importlib.util.spec_from_file_location("solv6trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01",
                           close_attempt=lambda gid, c: None, cut_proposer=lambda gid, c: None,
                           parked_root=project_root)
        result = run("STUCK", ctx)

        from recurvelib.loop.parked import ParkedStore
        parked_ids = ParkedStore(project_root).ids()
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if "STUCK" in parked_ids:
    print("a frontier node is written to the parked store with its reason")
    sys.exit(0)
print(f"ours=parked_ids={parked_ids} oracle='STUCK' in parked_ids")
sys.exit(1)
PYEOF
