#!/usr/bin/env bash
# TK-5: validate refuses an unfalsified probe (no trap, no waiver). The trap
# fixture flips enforcement off — and the same trap-less guard then passes,
# which this probe reports as RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
traps = "off" if fixture else "required"
with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    (t / "claims" / "x" / "probes").mkdir(parents=True)
    (t / "claims" / "x" / "probes" / "g.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (t / "claims" / "x" / "gaps.yaml").write_text(
        "- id: X-1\n  title: t\n  class: friction\n  status: closed\n"
        "  severity: cosmetic\n  reads: none\n  smallest_fix: f\n  probe: probes/g.sh\n")
    (t / "recurve.toml").write_text(
        '[project]\nname = "x"\ndefault_reads = "none"\n[target]\ntree = "."\n'
        f'[gate]\ntraps = "{traps}"\n[reads.none]\nmethod = "none"\n'
        '[suites.x]\ndir = "claims/x"\n')
    r = subprocess.run([sys.executable, str(Path(root) / "recurve"),
                        "--config", str(t / "recurve.toml"), "validate"],
                       capture_output=True, text=True)
if r.returncode == 1 and "never been seen RED" in r.stdout:
    print("unfalsified probe rejected by validate")
    sys.exit(0)
print("ours=trap-less guard accepted oracle=validate refuses "
      "(a probe never seen RED is not yet evidence)")
sys.exit(1)
PYEOF
