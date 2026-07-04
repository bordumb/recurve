#!/usr/bin/env bash
# EV-6: the orchestrator turns a run into ANALYZE-READY rows. It wraps the agent
# adapter and the held-out oracle into one unit: run the agent, read the final
# solution.py, grade it with quarantine.evaluate against the pinned oracle, and
# seal a row carrying BOTH `declared_done` and `oracle_verdict` plus per-row
# provenance (dataset revision, model verbatim, recurve commit, adapter version,
# seed) so any row is self-re-executable. `row_is_complete` refuses a row that
# would leave analyze without its dependent variable. Driven by a mock agent
# here — no live agent, no spend.
#
# RED until orchestrate exists. The trap is a declared_done-only row (the
# run-only schema) — row_is_complete must refuse it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.orchestrate import row_is_complete
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
# the current run-only schema: declared_done, no oracle_verdict / provenance
bad = {'cell_id':'c1','model':'m','arm':'A0','task_id':'t','declared_done':True,'agent_exit':0}
print('ACCEPTED' if row_is_complete(bad) else 'REFUSED')
" 2>&1)" || { echo "orchestrate incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REFUSED$'; then
    echo "row_is_complete refuses a declared_done-only row"; exit 1   # guard holds → RED
  fi
  echo "row_is_complete accepted an analyze-incomplete row (fixture claimed it does)"; exit 0
fi

out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.orchestrate import make_orchestrator, row_is_complete
    from evallib.taskstore import content_hash
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
import pathlib, tempfile

TEST=('from solution import add\nimport unittest\n'
      'class T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)\n')
task={'task_id':'t/add','instruct_prompt':'add','test':TEST}
pin=content_hash([task]); tasks_by_id={task['task_id']: task}
prov={'dataset_revision':'rev123','recurve_commit':'abc123','adapter_version':'0.1.0'}

def mock_agent(solution):
    def adapter(cell, ws):
        ws=pathlib.Path(ws); ws.mkdir(parents=True, exist_ok=True)
        (ws/'solution.py').write_text(solution)
        return {'declared_done':True,'agent_exit':0}
    return adapter

# correct solution → oracle pass; wrong solution → oracle fail
for sol, want in [('def add(a,b):\n return a+b\n','pass'), ('def add(a,b):\n return a-b\n','fail')]:
    orch=make_orchestrator(mock_agent(sol), tasks_by_id, pin, prov)
    cell={'cell_id':'c','model':'claude-haiku-4-5','arm':'A0','budget':60000,'seed':0,'task_id':'t/add'}
    row=orch(cell, pathlib.Path(tempfile.mkdtemp()))
    assert row['declared_done'] is True, row
    assert row['oracle_verdict']==want, (want,row)
    for k in ('dataset_revision','recurve_commit','adapter_version','model','seed'):
        assert k in row, ('missing provenance',k,row)
    assert row_is_complete(row), row
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "orchestrator produces analyze-ready rows (declared_done + oracle_verdict + provenance)"
  exit 0
fi
echo "ours=orchestrator wrong: $(printf '%s' "$out" | tail -1) oracle=merged agent+oracle row with provenance"
exit 1
