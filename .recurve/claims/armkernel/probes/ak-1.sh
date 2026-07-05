#!/usr/bin/env bash
# AK-1: ArmSpec replaces the flat {"recurve": bool, "config": dict} shape.
# A0 = (bare, self_report, enforced, none, off, off). A3 = (recurve_init, gate,
# enforced, none, off, off). A7-A10 extend A3 by adversary=/governor= only,
# unchanged from today. The load-bearing claim: A0/A3/A7-A10 cells run through
# the NEW ArmSpec-driven kernel must produce BYTE-IDENTICAL rows to the
# pre-ArmSpec pipeline (ak-1.golden.json, captured from the real pre-refactor
# code before this claim existed) — a regression fixture, not an assertion
# taken on faith. Every field beyond the two required axes (workspace,
# done_signal) is defaulted, so a 7th axis added later needs no edit to any
# existing ArmSpec literal.
#
# RED-first: before ArmSpec existed, arm_spec()["recurve"]/["config"] was the
# only shape; this probe (and ak-1.golden.json) could not even be evaluated.
#
# With $TRAP_FIXTURE: a plausible wrong "kernel" that drops the
# only-non-default-ports-appear-in-the-row discipline, leaking boundary=/audit=
# columns onto EVERY row (even A0/A3's, which never asked for them) — the
# exact kind of accidental behavior change the regression fixture must catch.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
RECURVE="$REPO/recurve"
GOLDEN="$DIR/ak-1.golden.json"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import sys, json, tempfile, pathlib, dataclasses; sys.path.insert(0, EVAL)
from evallib.taskstore import content_hash
TASK={"task_id":"t/add","instruct_prompt":"write add(a,b) returning the sum",
      "test":"import unittest\n"
             "class T(unittest.TestCase):\n def test(self): self.assertEqual(task_func(1,2),3)\n"}
PINS={TASK["task_id"]: content_hash([TASK])}; TASKS={TASK["task_id"]:TASK}
PROV={"dataset_revision":"rev1","recurve_commit":"c1","adapter_version":"0.1.0","oracle_env_hash":"oeh:test"}
GOOD="def task_func(a,b):\n return a+b\n"
BAD="def task_func(a,b):\n return a-b\n"

def cell(arm, cell_id):
    return {"cell_id":cell_id,"model":"claude-haiku-4-5","arm":arm,
            "budget":60000,"seed":0,"task_id":TASK["task_id"]}

def claim(ws):
    p=ws/"claims"/"s"/"probes"; p.mkdir(parents=True, exist_ok=True)
    (p/"g-1.sh").write_text("#!/bin/sh\nexit 0\n")
    t=p/"g-1.trap"/"curated"; t.mkdir(parents=True, exist_ok=True); (t/"x").write_text("cx\n")

def gate_fn(ws):
    p=pathlib.Path(ws)/".gate"; return p.read_text().strip() if p.exists() else "red"

def bare_mock_ok(cell_, ws):
    ws=pathlib.Path(ws); (ws/"solution.py").write_text(GOOD)
    return {"terminated":True,"agent_exit":0,"stop_reason":"single_shot",
            "tokens_in":111,"tokens_out":222,"cost_usd":0.01}

def gated_mock_declared(cell_, ws):
    ws=pathlib.Path(ws); claim(ws); (ws/"solution.py").write_text(GOOD); (ws/".gate").write_text("green")
    return {"terminated":True,"agent_exit":0,"stop_reason":"gate_green",
            "tokens_in":333,"tokens_out":444,"cost_usd":0.02}

def gated_mock_refused(cell_, ws):
    ws=pathlib.Path(ws); claim(ws); (ws/"solution.py").write_text(BAD); (ws/".gate").write_text("red")
    return {"terminated":True,"agent_exit":0,"stop_reason":"budget_exhausted",
            "tokens_in":555,"tokens_out":666,"cost_usd":0.03}

def gated_mock_process_failed(cell_, ws):
    ws=pathlib.Path(ws); (ws/"solution.py").write_text(BAD); (ws/".gate").write_text("red")
    return {"terminated":True,"agent_exit":0,"stop_reason":"budget_exhausted",
            "tokens_in":10,"tokens_out":10,"cost_usd":0.001}

SCENARIOS = {
    "A0-declared": ("A0", bare_mock_ok, None),
    "A3-declared": ("A3", None, gated_mock_declared),
    "A3-refused": ("A3", None, gated_mock_refused),
    "A3-process_failed": ("A3", None, gated_mock_process_failed),
    "A7-declared": ("A7", None, gated_mock_declared),
    "A8-declared": ("A8", None, gated_mock_declared),
    "A9-declared": ("A9", None, gated_mock_declared),
    "A10-declared": ("A10", None, gated_mock_declared),
}

def run_all(make_orchestrator, materialize):
    rows = {}
    for name, (arm, bare, gated) in SCENARIOS.items():
        ws = pathlib.Path(tempfile.mkdtemp()) / "ws"
        materialize(TASKS[TASK["task_id"]], arm, ws, recurve_cmd=RECURVE)
        agent = gated if gated is not None else bare
        o = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=gate_fn)
        rows[name] = o(cell(arm, name), ws)
    return rows
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_orchestrate.py" ] || { echo "trap fixture missing broken_orchestrate.py"; exit 2; }
  out="$(EVAL="$EVAL" RECURVE="$RECURVE" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
import importlib.util
spec = importlib.util.spec_from_file_location('broken_orchestrate', '$TRAP_FIXTURE/broken_orchestrate.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from evallib.materialize import materialize

golden = json.load(open('$GOLDEN'))
rows = run_all(mod.make_orchestrator, materialize)
mismatches = [k for k in golden if rows.get(k) != golden[k]]
print('MISMATCH' if mismatches else 'MATCH', ','.join(mismatches))
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    MATCH*)
      echo "ours=rows matched the golden fixture despite the leaked default-port columns "\
           "oracle=must diverge — the fixture failed to exercise the intended bug"
      exit 0 ;;
    MISMATCH*)
      echo "ours=rows diverged from ak-1.golden.json ($out) oracle=byte-identical — "\
           "correctly caught the leaked boundary=/audit= columns"
      exit 1 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" RECURVE="$RECURVE" python3 -c "
EVAL='$EVAL'; RECURVE='$RECURVE'
$HELP
try:
    from evallib.arms import ArmSpec, arm_spec
    from evallib.orchestrate import make_orchestrator
    from evallib.materialize import materialize
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. ArmSpec's shape: workspace/done_signal required; everything else defaulted
# ('a 7th axis needs no edit to an existing literal' promise, verified
# structurally — every field but the first two carries a real default).
fields = dataclasses.fields(ArmSpec)
names = [f.name for f in fields]
assert names[:2] == ['workspace', 'done_signal'], names
for f in fields[2:]:
    if f.name == 'label':
        continue
    assert f.default is not dataclasses.MISSING, f'{f.name} has no default — a new arm would have to set it'

# 2. A0/A3's exact port tuple.
a0, a3 = arm_spec('A0'), arm_spec('A3')
assert (a0.workspace, a0.done_signal, a0.boundary, a0.audit, a0.adversary, a0.governor) == \
       ('bare', 'self_report', 'enforced', 'none', 'off', 'off'), a0
assert (a3.workspace, a3.done_signal, a3.boundary, a3.audit, a3.adversary, a3.governor) == \
       ('recurve_init', 'gate', 'enforced', 'none', 'off', 'off'), a3

# 3. A7-A10 extend A3 by adversary=/governor= ONLY.
for name, adv, gov in [('A7','cross_model','off'), ('A8','off','mechanical'),
                       ('A9','off','mechanical_review'), ('A10','cross_model','mechanical_review')]:
    s = arm_spec(name)
    assert s.workspace == a3.workspace and s.done_signal == a3.done_signal, (name, s)
    assert s.boundary == a3.boundary and s.audit == a3.audit, (name, s)
    assert s.adversary == adv and s.governor == gov, (name, s)

# 4. the actual regression fixture: A0/A3/A7-A10 cells, run through the NEW
# ArmSpec-driven kernel, byte-identical to the pre-ArmSpec golden capture.
golden = json.load(open('$GOLDEN'))
rows = run_all(make_orchestrator, materialize)
mismatches = {k: (rows.get(k), golden[k]) for k in golden if rows.get(k) != golden[k]}
assert not mismatches, f'byte-identical regression FAILED: {mismatches}'

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=ArmSpec/regression wrong: $(printf '%s' "$out"|tail -1) oracle=ArmSpec shape + A0/A3/A7-A10 port tuples + byte-identical rows"; exit 1; }
echo "ArmSpec replaces the flat dict; A0=(bare,self_report,enforced,none,off,off), A3=(recurve_init,gate,enforced,none,off,off), A7-A10 extend A3 by adversary=/governor= only — and A0/A3/A7-A10 cells are byte-identical to the pre-ArmSpec pipeline (regression fixture)"
exit 0
