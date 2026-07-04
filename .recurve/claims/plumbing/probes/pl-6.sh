#!/usr/bin/env bash
# PL-6: admission at the front — `recurve init --from-prd` admits the goal before it
# becomes claims. claimify.admit_result maps the parsed drafts to admission
# Assertions and runs admit(); run_claimify refuses/interviews a non-ADMIT goal
# instead of writing a brittle drafts suite, so an admission-refused goal never
# enters a cycle. RED-first: until the gate exists the probe is RED; a gate that
# ADMITs every goal (however vague) is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import re
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Verdict
    from recurvelib.claimify import ClaimifyResult, DraftClaim
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "atrap", Path(fixture) / "broken_admit.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        admit_result = mod.admit_result
    else:
        from recurvelib.claimify import admit_result
except ImportError:
    print("ours=no admission gate on claimify yet oracle=admit_result gates the PRD before drafts")
    sys.exit(1)  # RED-first


def draft(n, twin="the API accepts bad input", fork=""):
    return DraftClaim(n, f"t{n}", f"the API must reject bad input {n}", "prd",
                      "feature", "missing-surface", twin=twin, fork=fork)


gateable = ClaimifyResult(claims=[draft(1), draft(2), draft(3)])       # probe-able spine
vague = ClaimifyResult(claims=[draft(1, twin="", fork="what is 'good'?")])  # not gateable

try:
    g = admit_result(gateable).verdict
    v = admit_result(vague).verdict
except Exception as e:
    print(f"ours=admit_result raised {type(e).__name__} oracle=(ADMIT, not-ADMIT)")
    sys.exit(1)

if g == Verdict.ADMIT and v != Verdict.ADMIT:
    src = (Path(root) / "recurvelib" / "claimify.py").read_text()
    if "run_claimify" in src and re.search(r"admit_result|admit\(", src):
        print("admission gates claimify: gateable -> ADMIT, vague -> REFUSE, run_claimify consults it")
        sys.exit(0)
    print("ours=admit_result exists but run_claimify does not consult it "
          "oracle=claimify refuses a non-ADMIT goal before writing drafts")
    sys.exit(1)
print(f"ours=(gateable={g}, vague={v}) oracle=(ADMIT, not-ADMIT) — admission must refuse a vague goal")
sys.exit(1)
PYEOF
