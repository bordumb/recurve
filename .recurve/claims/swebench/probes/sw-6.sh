#!/usr/bin/env bash
# SW-6: the live smoke's MECHANISM — the one this suite can re-run forever
# hermetically. `swebench_pipeline.py` composes SW1-SW5 into a sibling
# orchestrator (never a fork of BigCodeBench's own): `expand_smoke_cells`
# produces 2 models x {SWE_A0, SWE_A9} x N instances, `make_swebench_
# orchestrator` seals analyze-complete rows with full provenance (including
# `oracle_env_hash`), and `assert_within_budget` is the spend trip-wire. The
# REAL live smoke (real API calls, real docker, real spend) is a separate,
# actually-executed invocation — this probe proves the MACHINERY it runs
# through is sound, the same way EV-23/24 test budget.py/watchdog.py
# hermetically and cite the real O6 run as validating evidence rather than
# re-executing it every gate run.
#
# RED-first: before evallib/swebench_pipeline.py existed, there was no
# SWE-bench-flavored orchestrator/cell-expansion/budget-trip-wire at all.
#
# With $TRAP_FIXTURE: a budget check that LOGS an overage and continues
# instead of halting — the real requirement must raise, not warn-and-proceed.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_budget_check.py" ] || { echo "trap fixture missing broken_budget_check.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_budget_check', '$TRAP_FIXTURE/broken_budget_check.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rows = [{'cost_usd': 10.0}, {'cost_usd': 20.0}]
try:
    total = mod.assert_within_budget(rows, 5.0)
    print('CONTINUED:' + str(total))
except mod.BudgetCeilingExceeded:
    print('HALTED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  last_line="$(printf '%s\n' "$out" | tail -1)"
  case "$last_line" in
    CONTINUED:*)
      echo "ours=broken budget check warned and kept running $ over ceiling "\
           "oracle=must raise BudgetCeilingExceeded — correctly caught the silent-overspend bug"
      exit 1 ;;
    HALTED)
      echo "ours=broken_budget_check unexpectedly halted oracle=the fixture failed to exercise the silent-overspend bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys, tempfile, subprocess, json as _json
sys.path.insert(0, '$EVAL')
try:
    from evallib.swebench_pipeline import (
        expand_smoke_cells, make_swebench_orchestrator, row_is_complete,
        assert_within_budget, BudgetCeilingExceeded, reviewer_model_for,
        SWE_A0, SWE_A9, SWE_MODELS_DEFAULT,
    )
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
from pathlib import Path

INSTANCES = ['pallets__flask-5014', 'psf__requests-5414', 'pylint-dev__pylint-4970']

# 1. the cross product: 3 instances x 2 models x {A0, A9} = 12 cells.
cells = expand_smoke_cells(INSTANCES, budget=4.0)
assert len(cells) == 12, len(cells)
assert {c['arm'] for c in cells} == {'A0', 'A9'}, {c['arm'] for c in cells}
assert {c['model'] for c in cells} == set(SWE_MODELS_DEFAULT)
assert {c['task_id'] for c in cells} == set(INSTANCES)

# 2. A9 is A3 + governor=mechanical_review, workspace repointed -- reused,
# never rebuilt; A0/A9 share the SAME workspace port.
assert SWE_A9.governor == 'mechanical_review' and SWE_A9.done_signal == 'gate'
assert SWE_A0.workspace == SWE_A9.workspace == 'swe_bench_repo'

# 3. the reviewer is genuinely a DIFFERENT model from the actor.
for m in SWE_MODELS_DEFAULT:
    assert reviewer_model_for(m) != m

# 4. end to end (fakes only -- no docker, no spend): both arms seal
# analyze-complete rows with full provenance including oracle_env_hash.
instance = {
    'instance_id': 'pallets__flask-5014', 'repo': 'pallets/flask', 'version': '2.3',
    'base_commit': 'abc', 'environment_setup_commit': 'def',
    'problem_statement': 'p', 'test_patch': 'diff\n+x\n', 'patch': 'diff\n+y\n',
    'FAIL_TO_PASS': ['t::f'], 'PASS_TO_PASS': [],
}
lock = {'digest': 'sha256:deadbeef', 'environment_image_hash': 'eih:fixture'}
instances_by_id = {'pallets__flask-5014': instance}
locks = {'pallets__flask-5014': lock}
prov = {'dataset_revision': 'rev1', 'recurve_commit': 'c1', 'adapter_version': '0.1.0'}

def make_ws():
    ws = Path(tempfile.mkdtemp()) / 'ws'
    (ws / 'testbed').mkdir(parents=True)
    subprocess.run(['git', 'init', '-q'], cwd=ws/'testbed', check=True)
    (ws/'testbed'/'f.py').write_text('a\n')
    subprocess.run(['git', 'add', '-A'], cwd=ws/'testbed', check=True)
    subprocess.run(['git', '-c','user.email=a@b.com','-c','user.name=t','commit','-q','-m','i'], cwd=ws/'testbed', check=True)
    (ws/'testbed'/'f.py').write_text('b\n')
    return ws

def fake_agent(cell, workspace):
    return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'single_shot',
            'tokens_in': 10, 'tokens_out': 5, 'cost_usd': 1.5, 'container_id': 'agentc'}
def fake_grader(inst, diff_text, digest, agent_container_id=None):
    return {'resolved': True, 'report': {}, 'grading_container_id': 'freshc'}
def fake_gate_fn(ws):
    return 'green'

rows = []
o0 = make_swebench_orchestrator(fake_agent, instances_by_id, locks, prov, grader=fake_grader)
rows.append(o0({**cells[0], 'task_id': 'pallets__flask-5014', '_arm_spec': SWE_A0}, make_ws()))
o9 = make_swebench_orchestrator(fake_agent, instances_by_id, locks, prov, grader=fake_grader, gate_fn=fake_gate_fn)
rows.append(o9({**cells[0], 'task_id': 'pallets__flask-5014', 'arm': 'A9', '_arm_spec': SWE_A9}, make_ws()))

for r in rows:
    assert row_is_complete(r), r
    assert r['oracle_env_hash'] == 'eih:fixture', r
    assert 'diff' in r and r['diff'], r

# 5. the budget trip-wire: under ceiling returns the total; over ceiling halts.
total = assert_within_budget(rows, 5.0)
assert abs(total - 3.0) < 1e-9, total
try:
    assert_within_budget(rows, 1.0)
    raise AssertionError('over-ceiling spend was NOT halted')
except BudgetCeilingExceeded:
    pass

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW6 smoke mechanism wrong: $(printf '%s' "$out"|tail -1) oracle=2 models x {A0,A9} x N instances seal complete rows; overspend halts, not warns"; exit 1; }
echo "smoke mechanism sound: 2 models x {A0, A9} x 3 instances = 12 cells; both arms seal analyze-complete rows with full provenance; overspend halts rather than warns-and-continues"
exit 0
