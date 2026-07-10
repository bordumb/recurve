#!/usr/bin/env bash
# SUFF-6: write_lean_assembly_scaffold refuses to clobber a DIFFERENT claim's real probe
# (docs/plans/autonomous_solver.md — found empirically: on a case-insensitive-but-preserving
# filesystem, an assembly_id that case-collides with an existing claim's slug silently
# overwrote that claim's real probe/check/trap files).
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


def make_config(tmpdir):
    toml_path = Path(tmpdir) / "recurve.toml"
    toml_path.write_text(textwrap.dedent("""\
        [project]
        name = "collision-test"
        [target]
        tree = "."
        [reads.none]
        method = "none"
        [suites.demo]
        dir = "demo"
        """))
    suite_dir = Path(tmpdir) / "demo"
    (suite_dir / "probes").mkdir(parents=True, exist_ok=True)
    # An EXISTING claim, "OTHER-CLAIM", whose probe slug is lowercase — the exact shape a
    # real navier_stokes claim's probe filename takes.
    (suite_dir / "probes" / "other-claim.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (suite_dir / "gaps.yaml").write_text(
        "- id: OTHER-CLAIM\n"
        "  title: pre-existing claim\n"
        "  class: missing-surface\n"
        "  status: closed\n"
        "  severity: feature\n"
        "  reads: none\n"
        "  smallest_fix: n/a\n"
        "  probe: probes/other-claim.sh\n"
    )
    return load(toml_path)


try:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)

        # A DIFFERENT, freshly-proposed claim whose assembly_id case-collides with
        # OTHER-CLAIM's own probe slug ("other-claim") on a case-insensitive-but-
        # preserving filesystem — a genuine CASE collision, not an exact-id match
        # (which is the legitimate re-derivation case this guard must NOT block).
        cut = Cut(
            parent_id="SOME-PARENT", goal_statement="True", leaves=(),
            assembly_proof="trivial", suite="demo", lean_module="Demo.Colliding",
            assembly_id="Other-Claim",
        )

        if fixture:
            spec = importlib.util.spec_from_file_location("suff6trap", Path(fixture) / "broken_write_scaffold.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            write_scaffold = mod.write_lean_assembly_scaffold
        else:
            from recurvelib.analysis.sufficiency import write_lean_assembly_scaffold as write_scaffold

        raised = False
        try:
            write_scaffold(cut, config)
        except ValueError:
            raised = True

        real_probe_untouched = (
            (Path(tmpdir) / "demo" / "probes" / "other-claim.sh").read_text() == "#!/usr/bin/env bash\nexit 0\n"
        )
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if raised and real_probe_untouched:
    print("collision refused before any file was written — the real claim's probe is untouched")
    sys.exit(0)
print(f"ours=raised={raised} real_probe_untouched={real_probe_untouched} "
      f"oracle=raised=True real_probe_untouched=True (a case-colliding assembly_id must never "
      f"silently overwrite a different claim's real probe)")
sys.exit(1)
PYEOF
