#!/usr/bin/env bash
# EV-16: calibration is the structural defense against the whole class of harness
# bug that biases toward the paper's headline. Canonical solutions cannot be
# wrong, so grading all of them through the finished oracle path must come back
# ~100% pass; any bug that turns correct solutions into errors drops that rate. No
# paid cell runs while the calibration for the current oracle env is RED. Teeth:
#   - a non-pass canonical must be a REGISTERED exclusion (pre-authored, with a
#     reason); an UNEXPLAINED failure refuses calibration outright — the strongest
#     tooth, a harness bug or undocumented exclusion cannot slip through;
#   - derive_calibration also refuses when the non-pass fraction exceeds a cap
#     (belt-and-suspenders), records the exclusion REASONS, content-hashes the
#     registered table (editing it later is detectable), and derives the timeout
#     from the canonical p99 (not guessed);
#   - calibration_admits_spend refuses at every boundary: no calibration, a
#     different oracle env (stale key), a different dataset, an edited exclusion
#     table, or a pass rate below the bar.
# Keyed by (oracle_env_hash, dataset_hash) so a changed oracle auto-invalidates.
# Hermetic — the real run is oracle-waived; this is the decision logic.
#
# RED until calibration exists. Traps: a stale-key calibration admits spend; an
# edited exclusion table admits spend; a harness that fails most canonicals
# calibrates by registering them all; an UNEXPLAINED canonical failure calibrates.
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
def registered(n_fail):
    return {f"BigCodeBench/f{i}":"requires-live-network" for i in range(n_fail)}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo stale_calibration)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc=\"$scenario\"
if sc==\"stale_calibration\":
    cal=derive_calibration(OEH, DH, results(96,4), registered(4))
    try:
        calibration_admits_spend(cal, oracle_env_hash=\"oeh:OTHER\", dataset_hash=DH,
                                  exclusions_content=registered(4)); print(\"ADMITTED\")
    except CalibrationError: print(\"REFUSED\")
elif sc==\"edited_exclusions\":
    cal=derive_calibration(OEH, DH, results(96,4), registered(4))
    tampered=dict(registered(4)); tampered[\"BigCodeBench/sneak\"]=\"x\"    # edit the table
    try:
        calibration_admits_spend(cal, oracle_env_hash=OEH, dataset_hash=DH,
                                  exclusions_content=tampered); print(\"ADMITTED\")
    except CalibrationError: print(\"REFUSED\")
elif sc==\"harness_bug_excluded\":
    try:
        derive_calibration(OEH, DH, results(10,90), registered(90))   # 90% fail, all registered
        print(\"CALIBRATED\")
    except CalibrationError: print(\"REFUSED\")
elif sc==\"unexplained_failure\":
    try:
        derive_calibration(OEH, DH, results(96,4), registered(2))     # 4 fail, only 2 explained
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

# a healthy calibration: 96 pass, 4 registered exclusions with reasons, derived timeout
cal=derive_calibration(OEH, DH, results(96,4,sec=2.0), registered(4))
assert cal[\"oracle_env_hash\"]==OEH and cal[\"dataset_hash\"]==DH and cal[\"n_tasks\"]==100, cal
assert len(cal[\"exclusions\"])==4 and abs(cal[\"raw_pass_rate\"]-0.96)<1e-9, cal
assert cal[\"exclusion_reasons\"][\"BigCodeBench/f0\"]==\"requires-live-network\", cal
assert cal[\"resolved_timeout\"] >= 2, cal
assert cal[\"exclusion_hash\"]==exclusion_content_hash(registered(4)), cal

# admits spend for the matching env + dataset + untouched exclusion table
adm=calibration_admits_spend(cal, oracle_env_hash=OEH, dataset_hash=DH, exclusions_content=registered(4))
assert adm==cal, adm

def refused(**kw):
    base=dict(oracle_env_hash=OEH, dataset_hash=DH, exclusions_content=registered(4))
    base.update(kw)
    try: calibration_admits_spend(cal, **base); return False
    except CalibrationError: return True
assert refused(oracle_env_hash=\"oeh:other\"), \"stale oracle env admitted\"
assert refused(dataset_hash=\"dh:other\"), \"different dataset admitted\"
tampered=dict(registered(4)); tampered[\"x\"]=\"y\"
assert refused(exclusions_content=tampered), \"edited exclusion table admitted\"
try: calibration_admits_spend(None, oracle_env_hash=OEH, dataset_hash=DH, exclusions_content={}); raise SystemExit(\"None admitted\")
except CalibrationError: pass

# TEETH: an UNEXPLAINED canonical failure (not registered) refuses calibration
try:
    derive_calibration(OEH, DH, results(96,4), registered(2)); raise SystemExit(\"unexplained failure calibrated\")
except CalibrationError: pass
# TEETH: a harness that fails most canonicals cannot calibrate even by registering them all (cap)
try:
    derive_calibration(OEH, DH, results(10,90), registered(90)); raise SystemExit(\"broken harness calibrated by exclusion\")
except CalibrationError: pass
# exclusion hash is order/format-invariant over the registered table
assert exclusion_content_hash({\"b\":\"1\",\"a\":\"2\"})==exclusion_content_hash({\"a\":\"2\",\"b\":\"1\"}), \"exclusion hash not order-invariant\"
print(\"OK\")
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=calibration wrong: $(printf '%s' "$out"|tail -1) oracle=unexplained failure refused, reasons recorded, admit refuses stale/edited/low-rate, keyed by (env,dataset)"; exit 1; }
echo "calibration: registered exclusions with reasons, unexplained failure refused, broken harness refused, admits only the matching env/dataset with untouched table"
exit 0
