#!/usr/bin/env bash
# EV-21 (O3-refine): two properties that keep calibration honest.
#  (a) The per-task timeout is max(floor, p99 x k), not a bare p99 x k — a suite
#      of trivially-fast canonicals must not yield a knife-edge timeout that flakes
#      a slow cell into an error under contention. floor and k are config knobs.
#  (b) Calibration must actually go RED on the grading-path bug class. The real
#      canonical solution (bcb-hard-854), graded the HISTORICAL wrong way
#      (solution + test as separate modules), comes back non-pass — and a
#      calibration built from that grading is REFUSED (unexplained failure). So a
#      wrapper that reintroduced the namespace bug could never pass calibration and
#      spend would stay blocked. The correct (shared-namespace) grading passes, and
#      its calibration is admitted. Hermetic: 854 is stdlib-only, graded under
#      sys.executable; no docker.
#
# RED until the floor + the regression coupling hold. Traps: a timeout that
# ignores the floor; a separate-modules regression that calibration fails to catch.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
FIX="$REPO/.recurve/claims/eval/fixtures/bcb-hard-854.json"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
[ -f "$FIX" ] || { echo "missing fixture $FIX"; exit 2; }

HELP='
import os, sys, json, tempfile, subprocess, pathlib; sys.path.insert(0, os.environ["EVAL"])
from evallib.calibration import derive_calibration, DEFAULT_TIMEOUT_FLOOR, CalibrationError
from evallib.smoke import load_fixture, grade_fixture
FX=load_fixture(os.environ["FIX"]); OEH="oeh:x"; DH="dh:x"
def res(verdicts, sec=1.0):   # {task_id: verdict} -> results dict
    return {t:{"verdict":v,"seconds":sec} for t,v in verdicts.items()}
def grade_separate_modules(program, test, timeout=60):
    # the HISTORICAL bug: solution and test as SEPARATE modules (test cannot see task_func)
    d=pathlib.Path(tempfile.mkdtemp())
    (d/"solution.py").write_text(program); (d/"oracle_test.py").write_text(test)
    p=subprocess.run([sys.executable,"-m","unittest","oracle_test"],cwd=d,capture_output=True,text=True,timeout=timeout)
    return "pass" if p.returncode==0 else "nonpass"
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo timeout_ignores_floor)"
  out="$(EVAL="$EVAL" FIX="$FIX" python3 -c "
$HELP
sc='$scenario'
if sc=='timeout_ignores_floor':
    cal=derive_calibration(OEH, DH, res({'t':'pass'}, sec=0.001), {}, timeout_k=3.0, timeout_floor=30)
    print('FLOORED' if cal['resolved_timeout']>=30 else 'UNFLOORED')
elif sc=='regression_not_caught':
    v=grade_separate_modules(FX['canonical_program'], FX['test'])   # -> nonpass (the bug)
    try:
        derive_calibration(OEH, DH, res({FX['task_id']: v}), {})    # unregistered non-pass
        print('CALIBRATED')
    except CalibrationError: print('REFUSED')
" 2>&1)" || { echo "calibration incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    timeout_ignores_floor:FLOORED) echo "the per-task timeout respects the floor"; exit 1 ;;
    regression_not_caught:REFUSED) echo "a separate-modules regression turns calibration RED"; exit 1 ;;
    *) echo "calibration failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" FIX="$FIX" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# (a) timeout = max(floor, p99 x k): the floor dominates trivially-fast suites...
cal=derive_calibration(OEH, DH, res({'t':'pass'}, sec=0.001), {}, timeout_k=3.0, timeout_floor=30)
assert cal['resolved_timeout']==30, ('floor not applied', cal['resolved_timeout'])
# ...and p99 x k dominates a slow suite
cal2=derive_calibration(OEH, DH, res({'t':'pass'}, sec=100.0), {}, timeout_k=3.0, timeout_floor=30)
assert cal2['resolved_timeout']==300, ('p99 x k not applied', cal2['resolved_timeout'])

# (b) the CORRECT (shared-namespace) grading: canonical passes, mutant fails
good, bad = grade_fixture(FX, timeout=60)
assert good=='pass' and bad in ('fail','error'), (good, bad)
# a calibration over the correct grading (100% pass, no exclusions) is admitted
ok=derive_calibration(OEH, DH, res({FX['task_id']:'pass'}), {})
assert ok['raw_pass_rate']==1.0 and ok['exclusions']==[], ok

# the HISTORICAL separate-modules bug turns the canonical non-pass...
reg=grade_separate_modules(FX['canonical_program'], FX['test'])
assert reg=='nonpass', ('separate-modules did not break the canonical', reg)
# ...and a calibration built from that grading is REFUSED (unexplained failure)
try:
    derive_calibration(OEH, DH, res({FX['task_id']: reg}), {}); raise SystemExit('regression calibrated')
except CalibrationError: pass
# a deliberately broken canonical (the fixture mutant, graded fail) also fails calibration
try:
    derive_calibration(OEH, DH, res({FX['task_id']:'pass','m':'fail'}), {}); raise SystemExit('broken canonical calibrated')
except CalibrationError: pass
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=calibration-refine wrong: $(printf '%s' "$out"|tail -1) oracle=timeout floor + separate-modules regression turns calibration RED"; exit 1; }
echo "calibration: timeout is max(floor, p99 x k); a separate-modules regression or a broken canonical turns it RED"
exit 0
