#!/usr/bin/env bash
# EV-16: calibration is the structural defense against the whole class of harness
# bug that biases toward the paper's headline. Canonical solutions cannot be
# wrong, so grading all 148 through the finished oracle path must come back ~100%
# pass; any bug that turns correct solutions into errors drops that rate. The
# logic here gives calibration its teeth:
#   - derive_calibration REFUSES to produce a calibration when the non-pass
#     fraction exceeds a cap — a broken harness must not be able to "pass" by
#     excluding everything; the residual few env-flaky tasks become REGISTERED
#     exclusions (generated, content-hashed), and the timeout is derived from the
#     canonical p99 (not guessed);
#   - calibration_admits_spend refuses at every boundary: no calibration, a
#     calibration for a DIFFERENT oracle env (stale key), a different dataset, an
#     EDITED exclusion list (hash mismatch), or a pass rate below the bar.
# Keyed by (oracle_env_hash, dataset_hash), so a changed oracle auto-invalidates.
# Hermetic — the 148-task run is oracle-waived; this is the decision logic.
#
# RED until calibration exists. Traps: a stale-key calibration admits spend; an
# edited exclusion list admits spend; a harness that fails most canonicals still
# produces a calibration by excluding them.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys; sys.path.insert(0, os.environ["EVAL"])
from evallib.calibration import (derive_calibration, calibration_admits_spend,
                                 exclusion_content_hash, CalibrationError)
OEH="oeh:env1"; DH="dh:data1"
def results(n_pass, n_fail, sec=1.0):
    r={}
    for i in range(n_pass): r[f"BigCodeBench/{i}"]={"verdict":"pass","seconds":sec}
    for i in range(n_fail): r[f"BigCodeBench/f{i}"]={"verdict":"error","seconds":sec}
    return r
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo stale_calibration)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc=\"$scenario\"
if sc==\"stale_calibration\":
    cal=derive_calibration(OEH, DH, results(96,4))     # calibration for env1
    try:
        calibration_admits_spend(cal, oracle_env_hash=\"oeh:OTHER\", dataset_hash=DH,
                                  exclusions_content=cal[\"exclusions\"]); print(\"ADMITTED\")
    except CalibrationError: print(\"REFUSED\")
elif sc==\"edited_exclusions\":
    cal=derive_calibration(OEH, DH, results(96,4))
    tampered=list(cal[\"exclusions\"])+[\"BigCodeBench/sneak\"]     # edit the exclusion list
    try:
        calibration_admits_spend(cal, oracle_env_hash=OEH, dataset_hash=DH,
                                  exclusions_content=tampered); print(\"ADMITTED\")
    except CalibrationError: print(\"REFUSED\")
elif sc==\"harness_bug_excluded\":
    try:
        derive_calibration(OEH, DH, results(10,90))    # 90% canonical failures
        print(\"CALIBRATED\")
    except CalibrationError: print(\"REFUSED\")
" 2>&1)" || { echo "calibration incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    *:REFUSED) echo "calibration refuses the '$scenario' path"; exit 1 ;;
    *) echo "calibration admitted '$scenario' (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print(\"MISSING\", e); raise SystemExit(0)

# a healthy calibration: 96 pass, 4 env-flaky -> registered exclusions, derived timeout
cal=derive_calibration(OEH, DH, results(96,4,sec=2.0))
assert cal[\"oracle_env_hash\"]==OEH and cal[\"dataset_hash\"]==DH and cal[\"n_tasks\"]==100, cal
assert len(cal[\"exclusions\"])==4 and abs(cal[\"raw_pass_rate\"]-0.96)<1e-9, cal
assert cal[\"resolved_timeout\"] >= 2, cal                 # p99 * k, ceil, >= the canonical time
assert cal[\"exclusion_hash\"]==exclusion_content_hash(cal[\"exclusions\"]), cal

# admits spend for the matching env + dataset + untouched exclusions
adm=calibration_admits_spend(cal, oracle_env_hash=OEH, dataset_hash=DH, exclusions_content=cal[\"exclusions\"])
assert adm is cal or adm==cal, adm

def refused(**kw):
    base=dict(oracle_env_hash=OEH, dataset_hash=DH, exclusions_content=cal[\"exclusions\"])
    base.update(kw)
    try: calibration_admits_spend(cal, **base); return False
    except CalibrationError: return True

assert refused(oracle_env_hash=\"oeh:other\"), \"stale oracle env admitted\"
assert refused(dataset_hash=\"dh:other\"), \"different dataset admitted\"
assert refused(exclusions_content=list(cal[\"exclusions\"])+[\"x\"]), \"edited exclusions admitted\"
# no calibration at all -> no spend
try: calibration_admits_spend(None, oracle_env_hash=OEH, dataset_hash=DH, exclusions_content=[]); raise SystemExit(\"None admitted\")
except CalibrationError: pass

# TEETH: a harness that fails most canonicals cannot produce a calibration by excluding them
try:
    derive_calibration(OEH, DH, results(10,90)); raise SystemExit(\"broken harness calibrated by exclusion\")
except CalibrationError: pass
# exclusion hash is order-invariant
assert exclusion_content_hash([\"b\",\"a\"])==exclusion_content_hash([\"a\",\"b\"]), \"exclusion hash not order-invariant\"
print(\"OK\")
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=calibration wrong: $(printf '%s' "$out"|tail -1) oracle=derive refuses a broken harness, admit refuses stale/edited/low-rate, keyed by (env,dataset)"; exit 1; }
echo "calibration: derived timeout+exclusions, refuses a broken harness, admits spend only for the matching env/dataset with untouched exclusions"
exit 0
