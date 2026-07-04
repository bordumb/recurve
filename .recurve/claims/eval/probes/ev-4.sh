#!/usr/bin/env bash
# EV-4: the Quarantine evaluator runs the hidden unittest suite against the
# agent's final solution.py in isolation, 3× with a majority verdict and a
# reported flake rate — and refuses to grade with a tampered oracle: the test
# text it is about to run must match the pin recorded at fetch time (a checksum
# against the pinned dataset). The isolation is a subprocess here (the real run
# uses a separate bigcodebench venv), so this probe is hermetic.
#
# RED until quarantine exists. The trap edits the oracle's test text while
# keeping the original pin and proves evaluate refuses it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

BODY='
import sys
sys.path.insert(0, EVALPATH)
from evallib.taskstore import content_hash
from evallib.quarantine import oracle_verdict, evaluate, OracleTamperError

TEST = ("from solution import add\n"
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_sum(self): self.assertEqual(add(1,2), 3)\n")
GOOD = "def add(a, b):\n    return a + b\n"
BAD  = "def add(a, b):\n    return a - b\n"
task = {"task_id": "t/add", "instruct_prompt": "add(a,b)", "test": TEST}
pin = content_hash([task])
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$BODY
# tamper: edit the test the grader will run, but keep the original pin
tampered = dict(task); tampered['test'] = TEST.replace('add(1,2), 3', 'add(1,2), 999')
try:
    evaluate(tampered, GOOD, pin, runs=3)
except OracleTamperError:
    print('REFUSED')
else:
    print('GRADED')
" 2>&1)" || { echo "quarantine incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REFUSED$'; then
    echo "quarantine refuses a tampered oracle"; exit 1        # guard holds → RED
  fi
  echo "quarantine graded with a tampered oracle (fixture claimed it does)"; exit 0   # broken → trap fails
fi

out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$BODY
# a passing solution → 3x majority pass, zero flake
v = oracle_verdict(TEST, GOOD, runs=3)
assert v['verdict'] == 'pass' and v['flake_rate'] == 0.0, v
# a failing solution → fail
vb = oracle_verdict(TEST, BAD, runs=3)
assert vb['verdict'] == 'fail', vb
# evaluate honors the pin: correct pin grades, wrong pin refuses
res = evaluate(task, GOOD, pin, runs=3)
assert res['verdict'] == 'pass', res
try:
    evaluate(task, GOOD, 'deadbeef'*8, runs=3); raise SystemExit('graded with a wrong pin')
except OracleTamperError:
    pass
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "quarantine runs the hidden suite 3x (majority + flake) and refuses a tampered oracle"
  exit 0
fi
echo "ours=quarantine wrong: $(printf '%s' "$out" | tail -1) oracle=3x majority verdict + pinned-oracle tamper check"
exit 1
