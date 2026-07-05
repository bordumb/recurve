#!/usr/bin/env bash
# EV-15: every row records WHICH oracle graded it. The oracle-env hash (EV-14) is
# provenance on par with dataset_revision and recurve_commit: without it, two
# identical-looking rows could have been graded by different oracles and nothing
# would show it. The orchestrator stamps `oracle_env_hash` from provenance into
# every row, and `row_is_complete` refuses a row that lacks it — so "graded by
# which oracle?" is answerable per row, forever, by dereferencing the hash to the
# lock in the run dir. Hermetic (mock agent, no spend).
#
# RED until oracle_env_hash is a required, populated row field. Trap: a row
# without oracle_env_hash accepted as complete (the untraceable-oracle hole).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import sys, tempfile, pathlib; sys.path.insert(0, EVAL)
from evallib.taskstore import content_hash
TASK={"task_id":"t/add","instruct_prompt":"add",
      "test":"import unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(task_func(1,2),3)\n"}
PINS={TASK["task_id"]: content_hash([TASK])}; TASKS={TASK["task_id"]:TASK}
PROV={"dataset_revision":"rev1","recurve_commit":"c1","adapter_version":"0.1.0","oracle_env_hash":"oeh:abc123"}
def sol_ok(ws): (pathlib.Path(ws)/"solution.py").write_text("def task_func(a,b):\n return a+b\n")
def mock(cell, ws):
    ws=pathlib.Path(ws); ws.mkdir(parents=True, exist_ok=True); sol_ok(ws)
    return {"terminated":True,"agent_exit":0,"tokens_in":10,"tokens_out":5}
def cell(arm): return {"cell_id":"x","model":"claude-haiku-4-5","arm":arm,"budget":60000,"seed":0,"task_id":TASK["task_id"]}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'
$HELP
from evallib.orchestrate import row_is_complete
# a row complete in every OTHER respect but missing the oracle-env hash
row={'cell_id':'c','model':'m','arm':'A0','task_id':'t','declared_done':True,'oracle_verdict':'pass',
     'dataset_revision':'r','recurve_commit':'c','adapter_version':'0.1.0','seed':0}
print('ACCEPTED' if row_is_complete(row) else 'REFUSED')
" 2>&1)" || { echo "orchestrate incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REFUSED$'; then
    echo "row_is_complete refuses a row with no oracle_env_hash"; exit 1
  fi
  echo "row_is_complete accepted a row with no oracle_env_hash (fixture claimed it does)"; exit 0
fi

out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'
$HELP
try:
    from evallib.orchestrate import make_orchestrator, row_is_complete
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
o=make_orchestrator(mock, TASKS, PINS, PROV, gate_fn=lambda ws:'red')
r=o(cell('A0'), tempfile.mkdtemp())
# the row carries the oracle-env hash verbatim from provenance
assert r['oracle_env_hash']=='oeh:abc123', r
assert row_is_complete(r), r
# and a row lacking it is NOT complete
bad=dict(r); del bad['oracle_env_hash']
assert not row_is_complete(bad), 'row_is_complete tolerated a missing oracle_env_hash'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=row provenance wrong: $(printf '%s' "$out"|tail -1) oracle=every row carries oracle_env_hash and row_is_complete requires it"; exit 1; }
echo "every row records which oracle graded it (oracle_env_hash), required by row_is_complete"
exit 0
