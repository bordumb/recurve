#!/usr/bin/env bash
# EV-11: the held-out oracle grades in a CONFIGURABLE isolated interpreter, not
# whatever Python happens to run the eval tooling. Real BigCodeBench-Hard tests
# import heavy third-party libraries; they can only pass in a dedicated venv that
# has them, and that venv must NOT be forced to also carry the eval tooling's own
# (conflicting) deps. So `quarantine` runs the hidden suite under the interpreter
# named by RECURVE_ORACLE_PYTHON when set, falling back to sys.executable when not
# — and the pin check still refuses a tampered oracle regardless of interpreter.
#
# RED until _run_once honors RECURVE_ORACLE_PYTHON. Trap: an oracle that ignores
# the configured interpreter and silently grades under sys.executable (so a run
# whose venv is missing BCB deps would mis-grade every solution as an error).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

# A shim that IS a real interpreter but fingerprints every invocation: proof the
# oracle actually launched the configured python, not sys.executable.
shim_dir="$(mktemp -d)"
marker="$shim_dir/used"
shim="$shim_dir/oracle-python"
cat > "$shim" <<SHIM
#!/bin/sh
echo used >> "$marker"
exec "$(command -v python3)" "\$@"
SHIM
chmod +x "$shim"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  : > "$marker"
  out="$(RECURVE_ORACLE_PYTHON="$shim" EVAL="$EVAL" python3 -c "
import sys, os; sys.path.insert(0, os.environ['EVAL'])
from evallib.quarantine import oracle_verdict
test='from solution import add\nimport unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)\n'
oracle_verdict(test, 'def add(a,b):\n return a+b\n', runs=1, timeout=30)
" 2>&1)" || { echo "quarantine incomplete: $out"; exit 2; }
  if [ -s "$marker" ]; then
    echo "oracle ran under the configured RECURVE_ORACLE_PYTHON (shim fingerprinted)"; exit 1
  fi
  echo "oracle ignored RECURVE_ORACLE_PYTHON and used sys.executable (fixture claimed it does)"; exit 0
fi

: > "$marker"
out="$(RECURVE_ORACLE_PYTHON="$shim" EVAL="$EVAL" python3 -c "
import sys, os; sys.path.insert(0, os.environ['EVAL'])
try:
    from evallib.quarantine import oracle_verdict, evaluate, OracleTamperError
    from evallib.taskstore import content_hash
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
test='from solution import add\nimport unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)\n'
# grades correctly AND under the configured interpreter
r=oracle_verdict(test, 'def add(a,b):\n return a+b\n', runs=3, timeout=30)
assert r['verdict']=='pass', r
# tamper refusal holds regardless of which interpreter grades
task={'task_id':'t/add','instruct_prompt':'add','test':test}
try:
    evaluate(task, 'def add(a,b):\n return a+b\n', 'deadbeef', runs=1)
    raise SystemExit('tampered oracle graded')
except OracleTamperError: pass
# real pin still grades
assert evaluate(task, 'def add(a,b):\n return a+b\n', content_hash([task]), runs=1)['verdict']=='pass'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=quarantine wrong: $(printf '%s' "$out"|tail -1) oracle=grades under configured interpreter + tamper-refused"; exit 1; }
[ -s "$marker" ] || { echo "ours=oracle did not launch RECURVE_ORACLE_PYTHON oracle=must grade under the configured interpreter"; exit 1; }
# and it falls back to sys.executable when the env var is unset (no shim marker needed)
: > "$marker"
unset RECURVE_ORACLE_PYTHON
EVAL="$EVAL" python3 -c "
import sys, os; sys.path.insert(0, os.environ['EVAL'])
from evallib.quarantine import oracle_verdict
test='from solution import add\nimport unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)\n'
assert oracle_verdict(test, 'def add(a,b):\n return a+b\n', runs=1)['verdict']=='pass'
" || { echo "ours=oracle broken with no configured interpreter oracle=falls back to sys.executable"; exit 1; }
echo "oracle grades in the configured isolated interpreter (RECURVE_ORACLE_PYTHON), tamper-refused, sys.executable fallback"
exit 0
