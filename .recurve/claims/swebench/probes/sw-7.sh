#!/usr/bin/env bash
# SW-7: grading aggregates 3 independent verification runs into one
# majority-vote verdict, never a single run. SWE-bench's own test suites are
# not perfectly deterministic (timing, container-startup jitter,
# non-deterministic ordering) -- a single grading run cannot distinguish
# "the fix is wrong" from "this run hit a flaky test". `grade_with_
# majority_vote` runs the underlying grader 3 times and takes whichever
# verdict a strict majority agree on; `make_swebench_orchestrator`'s DEFAULT
# grader must actually BE this function, not a single-shot grader, or the
# vote never happens where it matters.
#
# RED-first: before evallib/swebench_majority.py existed, there was no
# aggregation step at all -- the orchestrator's default grader called the
# underlying grading function exactly once per cell.
#
# With $TRAP_FIXTURE: a function with the SAME return shape (resolved/runs/
# agreement/unanimous) that calls the underlying grader only ONCE and
# reports that single result as an agreed vote -- a flaky disagreeing run
# never gets a chance to be outvoted.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_majority.py" ] || { echo "trap fixture missing broken_majority.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_majority', '$TRAP_FIXTURE/broken_majority.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

calls = []
def counting_grader(inst, diff, digest, **kw):
    calls.append(1)
    return {'resolved': len(calls) != 2}  # run 2 would disagree, if it ever ran

result = mod.broken_grade_with_majority_vote({}, 'diff', 'sha256:x', grader=counting_grader, num_runs=3)
print(f'CALLS={len(calls)} AGREEMENT={result.get(\"agreement\")}')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    CALLS=1*)
      echo "ours=broken_majority called the underlying grader ONCE and reported it as a 3/3 vote "\
           "oracle=must call the grader num_runs times before returning a verdict — correctly caught the missing-vote bug"
      exit 1 ;;
    CALLS=3*)
      echo "ours=broken_majority unexpectedly called the grader 3 times oracle=the fixture failed to exercise the single-run bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
try:
    from evallib.swebench_majority import grade_with_majority_vote, NoMajorityError
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. unanimous pass -- every run agrees.
calls = []
def grader_all_pass(inst, diff, digest, **kw):
    calls.append(1); return {'resolved': True, 'report': {}, 'grading_container_id': f'c{len(calls)}'}
r = grade_with_majority_vote({}, 'd', 'sha256:x', grader=grader_all_pass)
assert len(calls) == 3, calls
assert r['resolved'] is True and r['unanimous'] is True and r['agreement'] == '3/3', r

# 2. a real 2-1 split -- the flaky-test scenario: the middle run disagrees,
# but the majority still resolves, and the split stays visible.
calls2 = []
def grader_flaky(inst, diff, digest, **kw):
    calls2.append(1); return {'resolved': len(calls2) != 2}
r2 = grade_with_majority_vote({}, 'd', 'sha256:x', grader=grader_flaky)
assert len(calls2) == 3, calls2
assert r2['resolved'] is True, r2
assert r2['unanimous'] is False and r2['agreement'] == '2/3', r2
assert len(r2['runs']) == 3, r2['runs']  # every individual run preserved, never dropped

# 3. majority fail -- 2 of 3 runs say no.
calls3 = []
def grader_mostly_fail(inst, diff, digest, **kw):
    calls3.append(1); return {'resolved': len(calls3) == 1}
r3 = grade_with_majority_vote({}, 'd', 'sha256:x', grader=grader_mostly_fail)
assert r3['resolved'] is False and r3['agreement'] == '2/3', r3

# 4. agent_container_id/model_name/timeout are forwarded to EVERY run, not
# just the first -- the reuse guard must see them on every attempt.
seen = []
def grader_capture(inst, diff, digest, **kw):
    seen.append(kw); return {'resolved': True}
grade_with_majority_vote({}, 'd', 'sha256:x', grader=grader_capture,
                          agent_container_id='agentc123', model_name='haiku', timeout=99)
assert len(seen) == 3
assert all(k.get('agent_container_id') == 'agentc123' for k in seen)
assert all(k.get('model_name') == 'haiku' for k in seen)

# 5. wiring: the orchestrator's DEFAULT grader (no explicit override) must
# actually run 3 verification passes per cell, not one -- the vote has to
# happen where grading really occurs, not just be available as a library
# function nobody calls. extract_diff is stubbed (a real git repo isn't
# needed to prove THIS: the point is how many times the grader runs, not
# what git produces -- avoids real subprocess/git load in the gate's
# fully-concurrent probe fleet).
import tempfile
from pathlib import Path
import evallib.swebench_majority as smaj
import evallib.swebench_pipeline as sp
from evallib.swebench_pipeline import SWE_A0

calls4 = []
def fake_underlying_grader(inst, diff_text, digest, *, agent_container_id=None,
                            model_name='agent', timeout=1800, client=None, log_dir=None):
    calls4.append(1)
    return {'resolved': len(calls4) != 3, 'report': {}, 'grading_container_id': f'f{len(calls4)}'}
smaj.grade_fresh = fake_underlying_grader  # the function grade_with_majority_vote falls back to
sp.extract_diff = lambda workspace: 'diff --git a/f.py b/f.py\n+x\n'

instance = {'instance_id': 'x', 'repo': 'r', 'version': '1', 'base_commit': 'a',
            'environment_setup_commit': 'a', 'problem_statement': 'p',
            'test_patch': 'd\n+x\n', 'patch': 'd\n+y\n', 'FAIL_TO_PASS': ['t'], 'PASS_TO_PASS': []}
lock = {'digest': 'sha256:deadbeef', 'environment_image_hash': 'eih:fixture'}
prov = {'dataset_revision': 'r1', 'recurve_commit': 'c1', 'adapter_version': '0.1.0'}

def make_ws():
    ws = Path(tempfile.mkdtemp()) / 'ws'
    (ws / 'testbed').mkdir(parents=True)
    return ws

def fake_agent(cell, workspace):
    return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'single_shot',
            'tokens_in': 10, 'tokens_out': 5, 'cost_usd': 1.5, 'container_id': 'agentc'}
def fake_gate_fn(ws):
    return 'green'

orch = sp.make_swebench_orchestrator(fake_agent, {'x': instance}, {'x': lock}, prov, gate_fn=fake_gate_fn)
cell = {'cell_id': 'c1', 'model': 'm', 'arm': 'A0', 'budget': 4.0, 'seed': 0, 'task_id': 'x', '_arm_spec': SWE_A0}
row = orch(cell, make_ws())
assert len(calls4) == 3, calls4  # the orchestrator's default grader now votes, not single-shot
assert row['oracle_verdict'] == 'pass', row  # 2/3 majority (run 3 disagreed)
assert row['oracle_agreement'] == '2/3', row
assert row['oracle_unanimous'] is False, row

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW7 majority-vote wrong: $(printf '%s' "$out"|tail -1) oracle=grading must run 3 independent verification passes and vote, every split staying visible in provenance"; exit 1; }
echo "grading aggregates 3 independent verification runs via majority vote; the orchestrator's default grader genuinely votes, not single-shot; split verdicts stay visible as oracle_agreement/oracle_unanimous"
exit 0
