#!/usr/bin/env bash
# SOLV-1: CLOSE is tried before DECOMPOSE (docs/plans/autonomous_solver.md §2.2 cost order).
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


def fake_sufficiency_check(cut, config, today, timeout_s=300):
    import yaml
    suite_dir = config.suite_for(cut.suite).dir
    ledger_path = suite_dir / "gaps.yaml"
    entries = yaml.safe_load(ledger_path.read_text()) or []
    entry = {
        "id": cut.assembly_id, "title": "fake", "class": "missing-surface",
        "status": "closed", "severity": "feature", "reads": "none",
        "smallest_fix": "n/a", "probe": "probes/fake.sh",
    }
    if cut.parent_id != cut.assembly_id:
        entry["covers_claim"] = [cut.parent_id]
    entries.append(entry)
    ledger_path.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True))

    class FakeResult:
        ok = True
        detail = f"fake GREEN for {cut.assembly_id}"
    return FakeResult()


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)
        calls = []

        def close_attempt(gap_id, ctx):
            calls.append(("close_attempt", gap_id))
            if gap_id == "ROOT":
                return Cut(parent_id="ROOT", goal_statement="g", leaves=(),
                           assembly_proof="exact trivial", suite="demo",
                           lean_module="Demo.Root", assembly_id="ROOT")
            return None

        def cut_proposer(gap_id, ctx):
            calls.append(("cut_proposer", gap_id))
            return Cut(parent_id="ROOT", goal_statement="g",
                       leaves=(Leaf(id="L1", statement="p", hypothesis_name="h1"),),
                       assembly_proof="exact trivial", suite="demo",
                       lean_module="Demo.RootAssembly")

        if fixture:
            spec = importlib.util.spec_from_file_location("solv1trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01", close_attempt=close_attempt,
                           cut_proposer=cut_proposer, sufficiency_check=fake_sufficiency_check)
        run("ROOT", ctx)

        decompose_ever_called = any(c[0] == "cut_proposer" for c in calls)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if not decompose_ever_called:
    print("close_attempt alone resolved ROOT — cut_proposer was never consulted")
    sys.exit(0)
print(f"ours=calls={calls} oracle=cut_proposer never called once close_attempt succeeds")
sys.exit(1)
PYEOF
