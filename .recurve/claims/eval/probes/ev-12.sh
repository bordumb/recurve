#!/usr/bin/env bash
# EV-12: the oracle grades the SUBSTRATE'S namespace. BigCodeBench concatenates
# the solution and the test into ONE module and runs it: the entry point
# (`task_func`) is a module global the test references directly — no `from
# solution import`. All 148 BCB-Hard tests do this (908 `task_func` refs, zero
# solution-module imports). An oracle that grades the solution and test as
# SEPARATE modules turns every correct real solution into an error — and, like
# every harness defect in this design, that error reads as an oracle failure and
# inflates shipped-bad-work, biasing toward the paper's own headline. So the
# permanent fixture is a REAL pinned BCB-Hard task with its REAL canonical
# solution (bcb-hard-854.json — pure math, deterministic, stdlib-only), not a
# hand-authored idealization that could quietly agree with the harness instead of
# the substrate.
#
# RED until quarantine grades via concatenation. Trap: separate-module grading —
# the canonical solution, which cannot be wrong, comes back error/fail.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
FIX="$REPO/.recurve/claims/eval/fixtures/bcb-hard-854.json"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
[ -f "$FIX" ] || { echo "missing fixture $FIX"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  # The bug: grade solution and test as SEPARATE modules. The real canonical
  # solution (which cannot be wrong) must then NOT come back 'pass'.
  out="$(FIX="$FIX" python3 -c "
import json, os, sys, subprocess, tempfile, pathlib
fx=json.load(open(os.environ['FIX']))
d=pathlib.Path(tempfile.mkdtemp())
(d/'solution.py').write_text(fx['canonical_program'])
(d/'oracle_test.py').write_text(fx['test'])          # separate module — the defect
p=subprocess.run([sys.executable,'-m','unittest','oracle_test','-v'],cwd=d,capture_output=True,text=True,timeout=60)
print('pass' if p.returncode==0 else 'not_pass')
" 2>&1)" || { echo "separate-module probe crashed: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^not_pass$'; then
    echo "separate-module grading turns the canonical solution non-pass (the bias-toward-headline bug)"; exit 1
  fi
  echo "separate-module grading still passed the canonical (fixture claimed it fails)"; exit 0
fi

out="$(FIX="$FIX" EVAL="$EVAL" python3 -c "
import json, os, sys
sys.path.insert(0, os.environ['EVAL'])
try:
    from evallib.quarantine import oracle_verdict
    from evallib.taskstore import content_hash
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
fx=json.load(open(os.environ['FIX']))
prog, test = fx['canonical_program'], fx['test']

# 1. the REAL canonical solution grades PASS (the calibration invariant in miniature)
r=oracle_verdict(test, prog, runs=3, timeout=60)
assert r['verdict']=='pass', ('canonical solution not graded pass', r)

# 2. a corrupted solution grades fail/error (the oracle actually discriminates)
broken=prog.replace('return sums, all_permutations', 'return [], all_permutations')
rb=oracle_verdict(test, broken, runs=1, timeout=60)
assert rb['verdict'] in ('fail','error'), ('corrupted solution not caught', rb)

# 3. the entry point lives in the SHARED namespace — the test references it directly,
#    it does NOT import a solution module (this is the substrate's real convention)
assert 'from solution import' not in test and 'import solution' not in test, 'fixture is not substrate-faithful'
assert fx['entry_point']+'(' in test, 'test does not call the entry point directly'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=oracle wrong: $(printf '%s' "$out"|tail -1) oracle=canonical BCB solution grades pass via shared-namespace concatenation"; exit 1; }
echo "oracle grades the substrate's namespace: real canonical solution passes, corruption caught, entry point shared not imported"
exit 0
