#!/usr/bin/env bash
# EV-10: the run pipeline is the CONDUCTOR `recurve run` drives — it composes the
# materializer (EV-2) and the orchestrator (EV-6) into one adapter so a cell goes
# task -> fresh quarantined workspace -> arm-appropriate agent -> held-out oracle
# -> one analyze-complete row, with NO gap where cmd_run could hand the runner an
# incomplete row (no oracle_verdict) and waste a paid run. Two invariants the
# conductor alone owns: the agent ALWAYS runs in a materialized workspace (it can
# see TASK.md before it writes a line), and the bare/gated agent choice keys on
# the arm's `recurve` PROPERTY, not its name. Driven by mock agents — no spend.
#
# RED until make_pipeline_adapter exists AND cmd_run drives it. Traps: an agent
# run in a workspace that was never materialized (blind); a differently-named
# gated arm routed to the bare agent (name-coupling).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
RECURVE="$REPO/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import sys, tempfile, pathlib, inspect; sys.path.insert(0, EVAL)
from evallib.taskstore import content_hash
TASK={"task_id":"t/add","instruct_prompt":"write add(a,b) returning the sum",
      "test":"import unittest\n"
             "class T(unittest.TestCase):\n def test(self): self.assertEqual(task_func(1,2),3)\n"}
PINS={TASK["task_id"]: content_hash([TASK])}; TASKS={TASK["task_id"]:TASK}
PROV={"dataset_revision":"rev1","recurve_commit":"c1","adapter_version":"0.1.0","oracle_env_hash":"oeh:test"}
GOOD="def task_func(a,b):\n return a+b\n"
def cell(arm): return {"cell_id":"x","model":"claude-haiku-4-5","arm":arm,
                       "budget":60000,"seed":0,"task_id":TASK["task_id"]}
def gate_fn(ws):
    p=pathlib.Path(ws)/".gate"; return p.read_text().strip() if p.exists() else "red"
def claim(ws):
    p=pathlib.Path(ws,"claims/s/probes"); p.mkdir(parents=True,exist_ok=True)
    (p/"g-1.sh").write_text("#!/bin/sh\nexit 0\n")
    t=p/"g-1.trap"/"curated"; t.mkdir(parents=True,exist_ok=True); (t/"x").write_text("cx\n")
# bare mock: records what it SAW (materialize must have run first) and solves.
def bare_mock(seen):
    def a(cell, ws):
        ws=pathlib.Path(ws)
        seen["saw_task"]=(ws/"TASK.md").exists() and TASK["instruct_prompt"] in (ws/"TASK.md").read_text()
        seen["ran"]="bare"; (ws/"solution.py").write_text(GOOD)
        return {"terminated":True,"agent_exit":0,"tokens_in":100,"tokens_out":50}
    return a
# gated mock: authors a claim + green gate and solves.
def gated_mock(seen):
    def a(cell, ws):
        ws=pathlib.Path(ws); seen["ran"]="gated"; claim(ws)
        (ws/"solution.py").write_text(GOOD); (ws/".gate").write_text("green")
        return {"terminated":True,"agent_exit":0,"stop_reason":"gate_green",
                "tokens_in":100,"tokens_out":50}
    return a
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo skips_materialize)"
  out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
from evallib.run_pipeline import make_pipeline_adapter
sc='$scenario'
if sc=='skips_materialize':
    seen={}
    adapter=make_pipeline_adapter(TASKS, PINS, PROV, budget=60000, recurve_cmd=RECURVE,
                                  bare_agent=bare_mock(seen), gated_agent=gated_mock({}),
                                  gate_fn=gate_fn)
    adapter(cell('A0'), tempfile.mkdtemp())
    print('SAW' if seen.get('saw_task') else 'BLIND')
elif sc=='routes_by_name':
    import evallib.arms as A; A._ARMS['gated_x']={'recurve':True,'config':{},'label':'x'}
    seen={}
    adapter=make_pipeline_adapter(TASKS, PINS, PROV, budget=60000, recurve_cmd=RECURVE,
                                  bare_agent=bare_mock({}), gated_agent=gated_mock(seen),
                                  gate_fn=gate_fn)
    adapter(cell('gated_x'), tempfile.mkdtemp())
    print('GATED' if seen.get('ran')=='gated' else 'BARE')
" 2>&1)" || { echo "pipeline incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    skips_materialize:SAW)   echo "pipeline materializes before the agent runs (agent saw TASK.md)"; exit 1 ;;
    routes_by_name:GATED)    echo "a differently-named gated arm still takes the gated agent"; exit 1 ;;
    *) echo "pipeline failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
try:
    from evallib.run_pipeline import make_pipeline_adapter
    from evallib.orchestrate import row_is_complete
    from evallib import cli
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# bare arm: materialize -> bare agent (which SAW the task) -> oracle -> complete row
seen={}
adapter=make_pipeline_adapter(TASKS, PINS, PROV, budget=60000, recurve_cmd=RECURVE,
                              bare_agent=bare_mock(seen), gated_agent=gated_mock({}), gate_fn=gate_fn)
r=adapter(cell('A0'), tempfile.mkdtemp())
assert seen.get('saw_task'), 'agent ran before materialize — it could not see TASK.md'
assert seen.get('ran')=='bare', 'bare arm did not take the bare agent'
assert r['declared_done'] and r['oracle_verdict']=='pass' and r['gate_outcome'] is None, r
assert row_is_complete(r) and r['dataset_revision']=='rev1', r

# gated arm: materialize (recurve-init'd) -> gated agent -> green gate -> declared
seen2={}
adapter2=make_pipeline_adapter(TASKS, PINS, PROV, budget=60000, recurve_cmd=RECURVE,
                               bare_agent=bare_mock({}), gated_agent=gated_mock(seen2), gate_fn=gate_fn)
r2=adapter2(cell('A3'), tempfile.mkdtemp())
assert seen2.get('ran')=='gated', 'gated arm did not take the gated agent'
assert r2['gate_outcome']=='declared' and r2['terminal_state']['gate']=='green', r2
assert r2['oracle_verdict']=='pass' and row_is_complete(r2), r2

# decoupling: a differently-named recurve arm takes the gated agent (property, not name)
import evallib.arms as A; A._ARMS['gated_x']={'recurve':True,'config':{},'label':'x'}
seen3={}
adapter3=make_pipeline_adapter(TASKS, PINS, PROV, budget=60000, recurve_cmd=RECURVE,
                               bare_agent=bare_mock({}), gated_agent=gated_mock(seen3), gate_fn=gate_fn)
adapter3(cell('gated_x'), tempfile.mkdtemp())
assert seen3.get('ran')=='gated', 'a differently-named gated arm was routed to the bare agent'

# the wiring is real: cmd_run drives make_pipeline_adapter (not the bare-only adapter)
src=inspect.getsource(cli.cmd_run)
assert 'make_pipeline_adapter' in src, 'cmd_run does not drive the pipeline adapter'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=pipeline wrong: $(printf '%s' "$out"|tail -1) oracle=materialize-first + arm-property routing + analyze-complete rows + cmd_run wired"; exit 1; }
echo "pipeline: materialize-first, arm-property routing (bare/gated), analyze-complete rows, cmd_run wired"
exit 0
