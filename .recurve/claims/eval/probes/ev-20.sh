#!/usr/bin/env bash
# EV-20 (O5): the permanent end-to-end smoke fixture is drawn from the SUBSTRATE,
# not hand-authored — so mock-vs-substrate drift is structurally impossible. The
# fixture (bcb-hard-854.json) is one real pinned BigCodeBench-Hard task with its
# real canonical solution and a committed known-bad mutant. `assert_fixture_faithful`
# refuses a fixture whose task id is absent from the pinned dataset, or whose test
# has drifted from the dataset's own test for that id — the two ways a fixture
# could quietly stop representing the substrate. `grade_fixture` runs the exact
# grading convention (shared-namespace task_func): the canonical grades PASS, the
# mutant grades FAIL, so the smoke can actually detect a bad solution. The
# fidelity check against the FULL pinned dataset is oracle-waived where the
# gitignored dataset is absent; the logic is tested hermetically here.
#
# RED until smoke helpers exist. Traps: a fixture task id absent from the pinned
# dataset accepted; the known-bad mutant grading anything but FAIL.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
FIX="$REPO/.recurve/claims/eval/fixtures/bcb-hard-854.json"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
[ -f "$FIX" ] || { echo "missing fixture $FIX"; exit 2; }

HELP='
import os, sys, json; sys.path.insert(0, os.environ["EVAL"])
from evallib.smoke import load_fixture, assert_fixture_faithful, grade_fixture, SmokeFidelityError
FX=load_fixture(os.environ["FIX"])
# a minimal in-memory "pinned dataset" that DOES contain the fixture task, verbatim test
DS_OK=[{"task_id":FX["task_id"],"instruct_prompt":"x","test":FX["test"]}]
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo absent_task)"
  out="$(EVAL="$EVAL" FIX="$FIX" python3 -c "
$HELP
sc='$scenario'
if sc=='absent_task':
    ds=[{'task_id':'BigCodeBench/OTHER','instruct_prompt':'x','test':'t'}]   # fixture task NOT present
    try: assert_fixture_faithful(FX, ds); print('ACCEPTED')
    except SmokeFidelityError: print('REFUSED')
elif sc=='mutant_passes':
    good, bad = grade_fixture(FX, timeout=60)
    print('MUTANT_FAIL' if bad in ('fail','error') else 'MUTANT_PASS')
" 2>&1)" || { echo "smoke incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    absent_task:REFUSED)    echo "assert_fixture_faithful refuses a fixture task absent from the pinned dataset"; exit 1 ;;
    mutant_passes:MUTANT_FAIL) echo "the known-bad mutant grades FAIL — the smoke can detect a bad solution"; exit 1 ;;
    *) echo "smoke failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" FIX="$FIX" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# the fixture is substrate-shaped: real task id, entry point referenced directly (no import),
# a canonical AND a committed known-bad mutant
assert FX['task_id'].startswith('BigCodeBench/'), FX['task_id']
assert 'from solution import' not in FX['test'] and FX['entry_point']+'(' in FX['test'], 'fixture not substrate-faithful'
assert FX['known_bad_program'] != FX['canonical_program'], 'no known-bad mutant'

# faithful to a dataset that contains it verbatim; refuses absence and drift
assert_fixture_faithful(FX, DS_OK)  # no raise
try: assert_fixture_faithful(FX, [{'task_id':'x','test':'t'}]); raise SystemExit('absent task accepted')
except SmokeFidelityError: pass
drifted=[{'task_id':FX['task_id'],'test':FX['test']+'# edited'}]
try: assert_fixture_faithful(FX, drifted); raise SystemExit('drifted test accepted')
except SmokeFidelityError: pass

# end-to-end: canonical PASSES, mutant FAILS (exact shared-namespace convention)
good, bad = grade_fixture(FX, timeout=60)
assert good=='pass', ('canonical did not pass', good)
assert bad in ('fail','error'), ('mutant not caught', bad)

# full-strength fidelity where the pinned dataset is present (oracle-waived otherwise)
import pathlib, glob
ds=sorted(glob.glob(os.path.join(os.environ['EVAL'],'datasets','bigcodebench-hard@*.jsonl')))
if ds:
    tasks=[json.loads(l) for l in open(ds[0]) if l.strip()]
    assert_fixture_faithful(FX, tasks)   # the fixture IS the substrate's task, byte-for-byte
    print('OK full')
else:
    print('OK waived')
" 2>&1)"
printf '%s\n' "$out" | grep -qE '^OK (full|waived)$' || { echo "ours=smoke fixture wrong: $(printf '%s' "$out"|tail -1) oracle=fixture from substrate (present+byte-match), canonical passes, mutant fails"; exit 1; }
tag="$(printf '%s\n' "$out" | grep -oE 'OK (full|waived)')"
echo "smoke fixture is a real substrate task ($tag fidelity): canonical passes, known-bad mutant fails, absence/drift refused"
exit 0
