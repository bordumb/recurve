#!/usr/bin/env bash
# SOLV-8: DISCOVER closes a node on a gate-confirmed candidate, and surfaces the frontier
# (never silently falls through to decompose) on a dry search (docs/plans/autonomous_solver.md §2.4).
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


def write_closed(config, suite, gap_id):
    import yaml
    suite_dir = config.suite_for(suite).dir
    ledger_path = suite_dir / "gaps.yaml"
    entries = yaml.safe_load(ledger_path.read_text()) or []
    entries.append({
        "id": gap_id, "title": "fake", "class": "missing-surface", "status": "closed",
        "severity": "feature", "reads": "none", "smallest_fix": "n/a", "probe": "probes/fake.sh",
    })
    ledger_path.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True))


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)
        decompose_called = []

        def discover_attempt(gap_id, ctx):
            if gap_id == "WITNESS-FOUND":
                write_closed(config, "demo", gap_id)  # simulates promote_candidate landing it
                return True
            if gap_id == "WITNESS-DRY":
                return False
            return None

        def cut_proposer(gap_id, ctx):
            decompose_called.append(gap_id)
            return None

        if fixture:
            spec = importlib.util.spec_from_file_location("solv8trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01",
                           close_attempt=lambda gid, c: None, cut_proposer=cut_proposer,
                           discover_attempt=discover_attempt)

        found = run("WITNESS-FOUND", ctx)
        dry = run("WITNESS-DRY", ctx)

        ledger = load_ledger(config)
        found_closed = (g := ledger.by_id("WITNESS-FOUND")) is not None and g.status is Status.CLOSED
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

ok = (found_closed and found.closed == ("WITNESS-FOUND",)
      and dry.frontier == ("WITNESS-DRY",) and dry.closed == ()
      and not decompose_called)
if ok:
    print("DISCOVER closes on a gate-confirmed candidate and surfaces frontier on a dry search, "
          "never falling through to decompose")
    sys.exit(0)
print(f"ours=found_closed={found_closed} found.closed={found.closed} dry.frontier={dry.frontier} "
      f"dry.closed={dry.closed} decompose_called={decompose_called}")
sys.exit(1)
PYEOF
