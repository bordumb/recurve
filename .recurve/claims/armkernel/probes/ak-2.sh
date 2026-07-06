#!/usr/bin/env bash
# AK-2: A0 and A6 are the SAME done_signal port ("self_report"), differing
# only in workspace — A6 does not get its own bespoke "ignore the gate"
# logic. A6's workspace is real (recurve init runs for real, a real ledger
# is present), but self_report never consults it: the gate function is
# called ZERO times, and even a genuinely red gate has zero effect on the
# recorded declared_done.
#
# RED-first: before self_report existed as a shared port, A6 had no arm
# entry and no done-signal concept could be "unconsulted" — there was
# nothing to measure.
#
# With $TRAP_FIXTURE: a self_report that gives A6 its own bespoke "peek at
# the gate if this looks like a recurve workspace" logic (a plausible bug:
# someone "helpfully" makes self_report smarter for recurve-initialized
# workspaces). The real requirement must catch this — self_report is
# supposed to be IDENTICAL for A0 and A6, full stop.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
RECURVE="$REPO/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import sys, tempfile, pathlib; sys.path.insert(0, EVAL)
from evallib.taskstore import content_hash
TASK={"task_id":"t/add","instruct_prompt":"write add(a,b) returning the sum",
      "test":"import unittest\n"
             "class T(unittest.TestCase):\n def test(self): self.assertEqual(task_func(1,2),3)\n"}
GOOD="def task_func(a,b):\n return a+b\n"

def cell(arm):
    return {"cell_id":"x","model":"claude-haiku-4-5","arm":arm,
            "budget":60000,"seed":0,"task_id":TASK["task_id"]}

def counting_gate_fn(calls):
    def gate_fn(ws):
        calls["n"] += 1
        return "red"   # if this is EVER consulted, it says the cell is not done
    return gate_fn
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_done_signal.py" ] || { echo "trap fixture missing broken_done_signal.py"; exit 2; }
  out="$(EVAL="$EVAL" RECURVE="$RECURVE" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
import importlib.util
spec = importlib.util.spec_from_file_location('broken_done_signal', '$TRAP_FIXTURE/broken_done_signal.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from evallib.materialize import materialize

ws = pathlib.Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A6', ws, recurve_cmd=RECURVE)
(ws / 'solution.py').write_text(GOOD)
calls = {'n': 0}
result = mod.self_report_done_signal(ws, {}, gate_fn=counting_gate_fn(calls))
print('CONSULTED' if calls['n'] > 0 or not result['declared_done'] else 'UNCONSULTED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    UNCONSULTED)
      echo "ours=self_report stayed unconsulted despite the gate-peeking bug "\
           "oracle=must consult (or flip declared_done) — the fixture failed to exercise the bug"
      exit 0 ;;
    CONSULTED)
      echo "ours=self_report consulted the gate (or flipped declared_done) for a recurve-looking "\
           "workspace oracle=must never — correctly caught the bespoke ignore-the-gate special case"
      exit 1 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" RECURVE="$RECURVE" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
try:
    from evallib.arms import arm_spec
    from evallib.done_signal import resolve_done_signal_port, self_report_done_signal
    from evallib.materialize import materialize
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. A6's exact port tuple: A3's workspace, self_report's done_signal.
a0, a3, a6 = arm_spec('A0'), arm_spec('A3'), arm_spec('A6')
assert a6.workspace == a3.workspace == 'recurve_init', a6
assert a6.done_signal == a0.done_signal == 'self_report', a6
assert a6.boundary == a3.boundary and a6.audit == a3.audit, a6
assert a6.adversary == a3.adversary and a6.governor == a3.governor, a6

# 2. genuine sharing: A0 and A6 resolve to the IDENTICAL function object —
# not two functions that merely behave alike.
assert resolve_done_signal_port(a0.done_signal) is resolve_done_signal_port(a6.done_signal) \
       is self_report_done_signal, 'A0/A6 do not share the same self_report function object'

# 3. A6's workspace is REAL: recurve init actually ran, a real ledger is present.
ws = pathlib.Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A6', ws, recurve_cmd=RECURVE)
assert (ws / '.recurve').exists() or (ws / 'recurve.toml').exists(), 'A6 workspace has no real ledger'
(ws / 'solution.py').write_text(GOOD)

# 4. self_report is UNCONSULTED: the gate function is called ZERO times, and
# even though it would say RED, declared_done is still True (solution.py
# alone decides).
calls = {'n': 0}
result = self_report_done_signal(ws, {}, gate_fn=counting_gate_fn(calls))
assert calls['n'] == 0, f'self_report consulted the gate {calls[\"n\"]} time(s) — it must never'
assert result['declared_done'] is True, result
assert result['gate_outcome'] is None and result['terminal_state'] == {}, result

# 5. the same holds end to end through the orchestrator for the real A6 arm
# (not just the port function in isolation) — a real red gate, zero effect.
from evallib.orchestrate import make_orchestrator
TASKS = {TASK['task_id']: TASK}
from evallib.taskstore import content_hash
PINS = {TASK['task_id']: content_hash([TASK])}
PROV = {'dataset_revision':'rev1','recurve_commit':'c1','adapter_version':'0.1.0','oracle_env_hash':'oeh:test'}
def agent(cell_, ws_):
    return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'single_shot',
            'tokens_in': 1, 'tokens_out': 1, 'cost_usd': 0.0}
calls2 = {'n': 0}
o = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=counting_gate_fn(calls2))
row = o(cell('A6'), ws)
assert calls2['n'] == 0, f'orchestrator consulted the gate for A6 ({calls2[\"n\"]} time(s))'
assert row['declared_done'] is True and row['gate_outcome'] is None, row

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=A6/self_report wrong: $(printf '%s' "$out"|tail -1) oracle=A6 shares A0's self_report function object, unconsulted, even under a red gate"; exit 1; }
echo "A0 and A6 share the SAME self_report done-signal function object; A6's real recurve ledger is present but never consulted — the gate is called zero times and a red verdict has zero effect on declared_done"
exit 0
