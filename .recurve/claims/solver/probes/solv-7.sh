#!/usr/bin/env bash
# SOLV-7: a refuted node is restated, not closed or decomposed as originally framed
# (docs/plans/autonomous_solver.md §2.1's restate_or_abandon).
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
import tempfile
import textwrap
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

from recurvelib.analysis.sufficiency import Cut
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
    entries.append({
        "id": cut.assembly_id, "title": "fake", "class": "missing-surface",
        "status": "closed", "severity": "feature", "reads": "none",
        "smallest_fix": "n/a", "probe": "probes/fake.sh",
    })
    ledger_path.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True))

    class FakeResult:
        ok = True
        detail = f"fake GREEN for {cut.assembly_id}"
    return FakeResult()


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)
        calls = []

        # WRONG-FRAMING's original statement is false as stated (the classic "SG vs FWD"
        # mix-up this claim guards against); CORRECTED-FRAMING is the fixed restatement,
        # directly closeable.
        def close_attempt(gap_id, ctx):
            calls.append(("close_attempt", gap_id))
            if gap_id == "CORRECTED-FRAMING":
                return Cut(parent_id="CORRECTED-FRAMING", goal_statement="g", leaves=(),
                           assembly_proof="exact trivial", suite="demo",
                           lean_module="Demo.Corrected", assembly_id="CORRECTED-FRAMING")
            return None

        def cut_proposer(gap_id, ctx):
            calls.append(("cut_proposer", gap_id))
            return None

        def refute_attempt(gap_id, ctx):
            return gap_id == "WRONG-FRAMING"

        def restate_attempt(gap_id, ctx):
            return "CORRECTED-FRAMING" if gap_id == "WRONG-FRAMING" else None

        if fixture:
            spec = importlib.util.spec_from_file_location("solv7trap", Path(fixture) / "broken_solve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.solve
        else:
            from recurvelib.loop.solver import solve as run

        from recurvelib.loop.solver import SolveContext
        ctx = SolveContext(config=config, today="2026-01-01", close_attempt=close_attempt,
                           cut_proposer=cut_proposer, sufficiency_check=fake_sufficiency_check,
                           refute_attempt=refute_attempt, restate_attempt=restate_attempt)
        run("WRONG-FRAMING", ctx)

        ledger = load_ledger(config)
        wrong_closed = (g := ledger.by_id("WRONG-FRAMING")) is not None and g.status is Status.CLOSED
        corrected_closed = (g := ledger.by_id("CORRECTED-FRAMING")) is not None and g.status is Status.CLOSED
        wrong_attempted_directly = ("close_attempt", "WRONG-FRAMING") in calls or ("cut_proposer", "WRONG-FRAMING") in calls
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if corrected_closed and not wrong_closed and not wrong_attempted_directly:
    print("refuted node was restated and closed under its corrected framing, never attempted as originally stated")
    sys.exit(0)
print(f"ours=wrong_closed={wrong_closed} corrected_closed={corrected_closed} "
      f"wrong_attempted_directly={wrong_attempted_directly} calls={calls} "
      f"oracle=wrong_closed=False corrected_closed=True wrong_attempted_directly=False")
sys.exit(1)
PYEOF
