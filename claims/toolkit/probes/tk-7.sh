#!/usr/bin/env bash
# TK-7: `next --json --lanes N` deals up to N lanes from pairwise-disjoint
# suites. Written RED-first: the surface's absence is RED (the claim is the
# surface), not BROKEN.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  # Counterexample: a lanes answer with two lanes in one suite. The same
  # disjointness check the accept path uses must reject it.
  python3 - "$TRAP_FIXTURE/lanes.json" <<'PYEOF'
import json
import sys

lanes = json.load(open(sys.argv[1])).get("lanes", [])
suites = [l.get("suite") for l in lanes]
if len(set(suites)) != len(suites):
    print("ours=two lanes share a suite oracle=pairwise-disjoint suites")
    sys.exit(1)
sys.exit(0)
PYEOF
  exit $?
fi
python3 - "$ROOT" <<'PYEOF'
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])


def probe(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(0o755)


with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    for s, gid in (("s1", "A-1"), ("s2", "B-1")):
        d = t / "claims" / s
        probe(d / "probes" / "p.sh", "echo ours=x oracle=y; exit 1")
        (d / "probes" / "p.trap" / "twin").mkdir(parents=True)
        (d / "gaps.yaml").write_text(
            f"- id: {gid}\n  title: t\n  class: missing-surface\n  status: open\n"
            f"  severity: feature\n  reads: none\n  smallest_fix: f\n  probe: probes/p.sh\n"
            # a second, lower-value gap in s1 ensures lanes pick per-suite tops
            + (f"- id: {gid}x\n  title: t2\n  class: friction\n  status: open\n"
               f"  severity: cosmetic\n  reads: none\n  smallest_fix: f\n  probe: probes/p.sh\n"
               if s == "s1" else ""))
    (t / "recurve.toml").write_text(
        '[project]\nname = "x"\ndefault_reads = "none"\n[target]\ntree = "."\n'
        '[gate]\ntraps = "off"\n[reads.none]\nmethod = "none"\n'
        '[suites.s1]\ndir = "claims/s1"\n[suites.s2]\ndir = "claims/s2"\n')
    r = subprocess.run([sys.executable, str(root / "recurve"), "--config",
                        str(t / "recurve.toml"), "next", "--json", "--lanes", "2"],
                       capture_output=True, text=True)
if r.returncode != 0:
    print("ours=no --lanes surface oracle=N disjoint-lane recommendations")
    sys.exit(1)
try:
    lanes = json.loads(r.stdout).get("lanes", [])
except json.JSONDecodeError:
    print("ours=non-JSON lanes answer oracle=machine-readable lanes")
    sys.exit(1)
suites = [l.get("suite") for l in lanes]
gaps = {l.get("gap") for l in lanes}
if len(lanes) != 2 or len(set(suites)) != 2:
    print(f"ours=lanes={lanes!r} oracle=2 lanes, pairwise-disjoint suites")
    sys.exit(1)
if gaps != {"A-1", "B-1"}:
    print(f"ours=gaps={sorted(gaps)} oracle=per-suite highest-value tops A-1,B-1")
    sys.exit(1)
print("lanes dealt from disjoint suites, value-first within each")
sys.exit(0)
PYEOF
