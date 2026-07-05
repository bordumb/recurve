#!/usr/bin/env bash
# EV-6: the orchestrator turns a run into ANALYZE-READY rows, in the order that
# must happen: run the agent, confirm it TERMINATED (never quarantine a live
# workspace), read solution.py, grade it against the pinned oracle, and seal a
# row with declared_done + oracle_verdict + (for a gated arm) terminal_state and
# its outcome class + provenance. The gated-vs-bare branch keys on the arm's
# `recurve` PROPERTY, not its name, so a manifest may name a gated arm anything.
# Driven by mock agents — no live agent, no spend.
#
# RED until the orchestrator does all of the above. Traps: an incomplete
# (declared-only) row accepted; a live (unterminated) workspace quarantined; a
# differently-named gated arm routed to the bare path (name-coupling).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import sys, tempfile, pathlib; sys.path.insert(0, EVAL)
from evallib.taskstore import content_hash
TASK={"task_id":"t/add","instruct_prompt":"add(a,b)",
      "test":"import unittest\n"
             "class T(unittest.TestCase):\n def test(self): self.assertEqual(task_func(1,2),3)\n"}
PINS={TASK["task_id"]: content_hash([TASK])}; TASKS={TASK["task_id"]:TASK}
PROV={"dataset_revision":"rev1","recurve_commit":"c1","adapter_version":"0.1.0"}
def sol_ok(ws): (pathlib.Path(ws)/"solution.py").write_text("def task_func(a,b):\n return a+b\n")
def sol_bad(ws): (pathlib.Path(ws)/"solution.py").write_text("def task_func(a,b):\n return a-b\n")
def gate(ws,v): (pathlib.Path(ws)/".gate").write_text(v)
def claim(ws):
    p=pathlib.Path(ws,"claims/s/probes"); p.mkdir(parents=True,exist_ok=True)
    (p/"g-1.sh").write_text("#!/bin/sh\nexit 0\n")
    t=p/"g-1.trap"/"curated"; t.mkdir(parents=True,exist_ok=True); (t/"x").write_text("cx\n")
def gate_fn(ws):
    p=pathlib.Path(ws)/".gate"; return p.read_text().strip() if p.exists() else "red"
def mock(setup, terminated=True, stop_reason=None):
    def adapter(cell, ws):
        ws=pathlib.Path(ws); ws.mkdir(parents=True, exist_ok=True); setup(ws)
        return {"terminated":terminated,"agent_exit":0,"stop_reason":stop_reason,
                "tokens_in":100,"tokens_out":50}
    return adapter
def cell(arm): return {"cell_id":"x","model":"claude-haiku-4-5","arm":arm,
                       "budget":60000,"seed":0,"task_id":TASK["task_id"]}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo incomplete_row)"
  out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'
$HELP
from evallib.orchestrate import make_orchestrator, row_is_complete, SequencingError
sc='$scenario'
if sc=='incomplete_row':
    bad={'cell_id':'c','model':'m','arm':'A0','task_id':'t','declared_done':True,'agent_exit':0}
    print('ACCEPTED' if row_is_complete(bad) else 'REFUSED')
elif sc=='live_workspace':
    o=make_orchestrator(mock(sol_ok, terminated=False), TASKS, PINS, PROV, gate_fn=gate_fn)
    try:
        o(cell('A0'), tempfile.mkdtemp()); print('QUARANTINED_LIVE')
    except SequencingError: print('REFUSED')
elif sc=='routes_by_name':
    import evallib.arms as A; A._ARMS['gated_x']={'recurve':True,'config':{},'label':'x'}
    o=make_orchestrator(mock(lambda w:(claim(w),sol_ok(w),gate(w,'green')), stop_reason='gate_green'),
                        TASKS, PINS, PROV, gate_fn=gate_fn)
    r=o(cell('gated_x'), tempfile.mkdtemp())
    print('GATED' if r.get('terminal_state') and r.get('gate_outcome')=='declared' else 'BARE')
" 2>&1)" || { echo "orchestrate incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    incomplete_row:REFUSED)    echo "row_is_complete refuses a declared-only row"; exit 1 ;;
    live_workspace:REFUSED)    echo "orchestrator refuses to quarantine a live workspace"; exit 1 ;;
    routes_by_name:GATED)      echo "a differently-named gated arm still takes the gated path"; exit 1 ;;
    *) echo "orchestrator failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'
$HELP
try:
    from evallib.orchestrate import make_orchestrator, row_is_complete, SequencingError
    from evallib.runner import run as run_matrix
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

def run(setup, arm, **kw):
    o=make_orchestrator(mock(setup, **kw), TASKS, PINS, PROV, gate_fn=gate_fn)
    return o(cell(arm), tempfile.mkdtemp())

# A0 declared: non-empty correct solution -> declared, oracle pass, no gate outcome
r=run(sol_ok,'A0'); assert r['declared_done'] and r['oracle_verdict']=='pass' and r['gate_outcome'] is None, r
# A3 declared: claim + green gate
r=run(lambda w:(claim(w),sol_ok(w),gate(w,'green')),'A3',stop_reason='gate_green')
assert r['gate_outcome']=='declared' and r['declared_done'] and r['terminal_state']['gate']=='green', r
# A3 refused: claim + red gate + budget exhaustion
r=run(lambda w:(claim(w),sol_bad(w),gate(w,'red')),'A3',stop_reason='budget_exhausted')
assert r['gate_outcome']=='gate_refused' and not r['declared_done'], r
# A3 process-failed: no claim + red gate
r=run(lambda w:(sol_bad(w),gate(w,'red')),'A3',stop_reason='budget_exhausted')
assert r['gate_outcome']=='process_failed' and not r['declared_done'], r
assert r['model']=='claude-haiku-4-5' and row_is_complete(r), r      # provenance verbatim + complete

# decoupling: a differently-named recurve arm takes the gated path (keys on property, not name)
import evallib.arms as A; A._ARMS['gated_x']={'recurve':True,'config':{},'label':'x'}
r=run(lambda w:(claim(w),sol_ok(w),gate(w,'green')),'gated_x',stop_reason='gate_green')
assert r['gate_outcome']=='declared' and r['terminal_state']=={'gate':'green','stop_reason':'gate_green'}, r

# sequencing: a live (unterminated) workspace is refused
try:
    run(sol_ok,'A0',terminated=False); raise SystemExit('quarantined a live workspace')
except SequencingError: pass

# resume through the orchestrator: zero new invocations on re-run
calls={'n':0}
def counting(cell,ws):
    calls['n']+=1; import pathlib; pathlib.Path(ws).mkdir(parents=True,exist_ok=True); sol_ok(ws)
    return {'terminated':True,'agent_exit':0}
o=make_orchestrator(counting, TASKS, PINS, PROV, gate_fn=gate_fn)
cs=[cell('A0')]; cs[0]['cell_id']='resume-1'
d=pathlib.Path(tempfile.mkdtemp())
run_matrix(cs, d/'r.jsonl', o, workspace_root=d/'cells'); first=calls['n']
run_matrix(cs, d/'r.jsonl', o, workspace_root=d/'cells')
assert calls['n']==first, 'resume re-invoked the agent'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=orchestrator wrong: $(printf '%s' "$out"|tail -1) oracle=all endings + sequencing + resume + decoupled routing"; exit 1; }
echo "orchestrator: all endings, terminal-state outcome, sequencing guard, resume, decoupled by arm property"
exit 0
