#!/usr/bin/env bash
# SUFF-7: sufficiency_ok promotes an ALREADY-LEDGERED gap open->closed once its own fresh
# probe measures GREEN (docs/plans/autonomous_solver.md — found empirically: run_baseline
# only ever processes gaps.draft.yaml, so a gap already in gaps.yaml was previously never
# promoted no matter what a fresh sufficiency_ok measurement said).
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
        name = "promote-test"
        [target]
        tree = "."
        [gate]
        traps = "off"
        [reads.none]
        method = "none"
        [suites.demo]
        dir = "demo"
        """))
    suite_dir = Path(tmpdir) / "demo"
    suite_dir.mkdir(parents=True, exist_ok=True)
    # ALREADY-LEDGERED, open — the exact shape re-deriving a real, existing claim takes.
    (suite_dir / "gaps.yaml").write_text(
        "- id: EXISTING-CLAIM\n"
        "  title: an already-ledgered, currently-open claim\n"
        "  class: missing-surface\n"
        "  status: open\n"
        "  severity: feature\n"
        "  reads: none\n"
        "  smallest_fix: n/a\n"
        "  probe: probes/existing-claim.sh\n"
    )
    return load(toml_path)


def fake_write_scaffold(cut, config):
    pass  # this claim's math is beside the point; the ledger write path is


class FakeResult:
    ok = True
    detail = "fake GREEN"


def fake_run_matrix_path(config, cut):
    # sufficiency_ok's own run_baseline/run_matrix calls need a REAL probe on disk that
    # reports GREEN, since promotion for an already-ledgered gap goes through the real
    # gate (traps=off here, deliberately, to isolate the promotion-write bug from trap
    # discipline — SUFF-repo's own suite already covers the trap-required path via the
    # real SUB-PROD-YOUNG re-derivation, docs/plans/autonomous_solver.md's acceptance run).
    probe_path = config.suite_for(cut.suite).dir / "probes" / "existing-claim.sh"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_text("#!/usr/bin/env bash\nexit 0\n")
    probe_path.chmod(0o755)


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)
        cut = Cut(
            parent_id="EXISTING-CLAIM", assembly_id="EXISTING-CLAIM",
            goal_statement="True", leaves=(), assembly_proof="trivial",
            suite="demo", lean_module="Demo.Existing",
        )
        fake_run_matrix_path(config, cut)

        if fixture:
            spec = importlib.util.spec_from_file_location("suff7trap", Path(fixture) / "broken_sufficiency_ok.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            run = mod.sufficiency_ok
        else:
            from recurvelib.analysis.sufficiency import sufficiency_ok as run

        result = run(cut, config, write_scaffold=fake_write_scaffold, today="2026-01-01")

        ledger = load_ledger(config)
        gap = ledger.by_id("EXISTING-CLAIM")
        status_after = gap.status if gap else None

        import yaml
        raw = yaml.safe_load((config.suite_for("demo").dir / "gaps.yaml").read_text())
        raw_status = next((e.get("status") for e in raw if e.get("id") == "EXISTING-CLAIM"), None)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if result.ok and status_after is Status.CLOSED and raw_status == "closed":
    print("an already-ledgered open claim was promoted to closed on disk after a fresh GREEN")
    sys.exit(0)
print(f"ours=result.ok={result.ok} status_after={status_after} raw_status={raw_status!r} "
      f"oracle=result.ok=True status_after=Status.CLOSED raw_status='closed'")
sys.exit(1)
PYEOF
