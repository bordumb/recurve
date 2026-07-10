#!/usr/bin/env bash
# SOLV-2: decompose recurses through every leaf and root-completion closes the root
# (docs/plans/autonomous_solver.md §2.1, §2.5 — zero human turns between leaves).
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
from recurvelib.core.model import Status, load_ledger


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

        root_cut = Cut(
            parent_id="ROOT", goal_statement="g",
            leaves=(Leaf(id="LEAF-1", statement="p1", hypothesis_name="h1"),
                    Leaf(id="LEAF-2", statement="p2", hypothesis_name="h2")),
            assembly_proof="exact trivial", suite="demo", lean_module="Demo.RootAssembly",
        )
        leaf_cuts = {
            "LEAF-1": Cut(parent_id="ROOT", goal_statement="p1", leaves=(),
                         assembly_proof="exact trivial", suite="demo",
                         lean_module="Demo.Leaf1", assembly_id="LEAF-1"),
            "LEAF-2": Cut(parent_id="ROOT", goal_statement="p2", leaves=(),
                         assembly_proof="exact trivial", suite="demo",
                         lean_module="Demo.Leaf2", assembly_id="LEAF-2"),
        }

        def close_attempt(gap_id, ctx):
            return leaf_cuts.get(gap_id)

        def cut_proposer(gap_id, ctx):
            return root_cut if gap_id == "ROOT" else None

        if fixture:
            spec = importlib.util.spec_from_file_location("solv2trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01", close_attempt=close_attempt,
                           cut_proposer=cut_proposer, sufficiency_check=fake_sufficiency_check)
        run("ROOT", ctx)

        ledger = load_ledger(config)
        root_gap = ledger.by_id("ROOT")
        root_closed = root_gap is not None and root_gap.status is Status.CLOSED
        leaves_closed = all(
            (g := ledger.by_id(lid)) is not None and g.status is Status.CLOSED
            for lid in ("LEAF-1", "LEAF-2")
        )
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if root_closed and leaves_closed:
    print("one solve() call closed both leaves and root-completion closed ROOT")
    sys.exit(0)
print(f"ours=root_closed={root_closed} leaves_closed={leaves_closed} "
      f"oracle=root_closed=True leaves_closed=True")
sys.exit(1)
PYEOF
