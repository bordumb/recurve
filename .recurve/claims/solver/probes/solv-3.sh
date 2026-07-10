#!/usr/bin/env bash
# SOLV-3: root-completion never fires on a partial child set (docs/plans/autonomous_solver.md
# §2.5) — regression guard for a real bug found while building the Phase 2 acceptance run.
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
    return load(toml_path), suite_dir


def write_ledger(suite_dir, entries):
    import yaml
    (suite_dir / "gaps.yaml").write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True))


def gap_entry(gid, parent_id):
    entry = {
        "id": gid, "title": "fake", "class": "missing-surface", "status": "closed",
        "severity": "feature", "reads": "none", "smallest_fix": "n/a", "probe": "probes/fake.sh",
    }
    if parent_id is not None and parent_id != gid:
        entry["covers_claim"] = [parent_id]
    return entry


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config, suite_dir = make_config(tmpdir)

        # ROOT's cut has TWO leaves + its own assembly. Only ONE leaf (LEAF-1) and the
        # assembly are closed so far — LEAF-2 has not even been armed yet (mirrors the exact
        # in-flight moment `solve` is in mid-recursion: the assembly closes at decompose
        # time, then leaves close one at a time).
        write_ledger(suite_dir, [
            gap_entry("ROOT-ASSEMBLY", "ROOT"),
            gap_entry("LEAF-1", "ROOT"),
        ])

        root_cut = Cut(
            parent_id="ROOT", goal_statement="g",
            leaves=(Leaf(id="LEAF-1", statement="p1", hypothesis_name="h1"),
                    Leaf(id="LEAF-2", statement="p2", hypothesis_name="h2")),
            assembly_proof="exact trivial", suite="demo", lean_module="Demo.RootAssembly",
        )

        def cut_proposer(gap_id, ctx):
            return root_cut if gap_id == "ROOT" else None

        if fixture:
            spec = importlib.util.spec_from_file_location("solv3trap", Path(fixture) / "broken_ready.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ready = mod.ready_to_assemble
        else:
            from recurvelib.loop.solver import SolveContext, _ready_to_assemble

            def ready(cut, ctx):
                return _ready_to_assemble(cut, ctx)

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01",
                           close_attempt=lambda gid, c: None, cut_proposer=cut_proposer)
        is_ready = ready(root_cut, ctx)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if not is_ready:
    print("correctly NOT ready — LEAF-2 hasn't closed (or even been armed) yet")
    sys.exit(0)
print("ours=ready_to_assemble=True oracle=False (LEAF-2 is not closed — a partial child set must never look ready)")
sys.exit(1)
PYEOF
