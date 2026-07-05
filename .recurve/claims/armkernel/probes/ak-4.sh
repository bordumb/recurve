#!/usr/bin/env bash
# AK-4: DoneSignalPort["external_ci"] is genuinely CLI-expressed — grading
# via an external command requires ZERO new Python. A trivial fixture
# ("test -f solution.py") as the configured command proves this end to end;
# swapping in a completely different command (a Python syntax check) proves
# the SAME port function serves both, with no new adapter code for either.
#
# RED-first: before this port existed, there was no config-string mechanism
# for "the repo's own tests decide" at all — every done-signal was Python
# logic (the gate, or self_report), never a delegated external command.
#
# With $TRAP_FIXTURE: an external_ci that "helpfully" also requires a
# non-empty solution.py regardless of what the command itself checks — a
# second, undeclared authority smuggled into what must be a PURE CLI
# contract (the command is the sole decision-maker). The real requirement
# must catch this.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_done_signal.py" ] || { echo "trap fixture missing broken_done_signal.py"; exit 2; }
  out="$(python3 -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_done_signal', '$TRAP_FIXTURE/broken_done_signal.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# command always exits 0 (a real benchmark's CI saying 'pass'); the
# workspace has NO solution.py at all. The command alone should be
# authoritative — declared_done must be True. The broken port silently
# requires solution.py too, so it will say False instead.
ws = Path(tempfile.mkdtemp())
result = mod.external_ci_done_signal(ws, {}, command='true')
print('MATCHES_COMMAND' if result['declared_done'] is True else 'DIVERGED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    MATCHES_COMMAND)
      echo "ours=declared_done followed the command alone despite the smuggled solution.py check "\
           "oracle=must diverge — the fixture failed to exercise the intended bug"
      exit 0 ;;
    DIVERGED)
      echo "ours=declared_done was False even though the configured command exited 0 "\
           "oracle=the command must be the sole authority — correctly caught the smuggled second check"
      exit 1 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(python3 -c "
import sys, tempfile, time
from pathlib import Path
sys.path.insert(0, '$EVAL')
try:
    from evallib.done_signal import external_ci_done_signal, resolve_done_signal_port
    from evallib.arms import ArmSpec
    from evallib.orchestrate import make_orchestrator
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. the trivial fixture: 'test -f solution.py' — exit 0 = done, exit 1 = not yet.
ws = Path(tempfile.mkdtemp())
r = external_ci_done_signal(ws, {}, command='test -f solution.py')
assert r['declared_done'] is False, r    # no solution.py yet
assert r['gate_outcome'] is None and r['terminal_state']['external_ci_returncode'] != 0, r
(ws / 'solution.py').write_text('x')
r2 = external_ci_done_signal(ws, {}, command='test -f solution.py')
assert r2['declared_done'] is True, r2
assert r2['terminal_state']['external_ci_returncode'] == 0, r2

# 2. a COMPLETELY DIFFERENT command — zero new Python needed for this one
# either; the SAME port function serves it.
ws2 = Path(tempfile.mkdtemp())
(ws2 / 'solution.py').write_text('def f(a, b):\n    return a + b\n')   # valid python
ok = external_ci_done_signal(ws2, {}, command='python3 -m py_compile solution.py')
assert ok['declared_done'] is True, ok
(ws2 / 'solution.py').write_text('def f(a, b:\n    return a + b\n')   # syntax error
bad = external_ci_done_signal(ws2, {}, command='python3 -m py_compile solution.py')
assert bad['declared_done'] is False, bad

# 3. no command configured -> fails loud, not a silent False.
try:
    external_ci_done_signal(Path(tempfile.mkdtemp()), {}, command='')
    raise AssertionError('empty command was accepted')
except ValueError:
    pass

# 4. a hanging command is bounded by timeout, mapped to a returncode (124),
# never left to hang the caller.
t0 = time.monotonic()
timed_out = external_ci_done_signal(Path(tempfile.mkdtemp()), {}, command='sleep 5', timeout=1)
elapsed = time.monotonic() - t0
assert elapsed < 4, f'timeout was not honored: took {elapsed}s'
assert timed_out['declared_done'] is False, timed_out
assert timed_out['terminal_state']['external_ci_returncode'] == 124, timed_out

# 5. resolves through the same registry every other done_signal does.
assert resolve_done_signal_port('external_ci') is external_ci_done_signal

# 6. end to end through the real orchestrator, with an ArmSpec constructed
# directly (this port closes A1's mechanism gap without needing a named A1
# arm entry — the config string IS the mechanism).
spec = ArmSpec(workspace='bare', done_signal='external_ci', external_ci_command='test -f solution.py')
assert spec.done_signal == 'external_ci' and spec.external_ci_command, spec
import evallib.arms as A
A._ARMS['_AK4_PROBE_ONLY'] = spec
try:
    from evallib.taskstore import content_hash
    TASK = {'task_id': 't/x', 'instruct_prompt': 'x', 'test': ''}
    TASKS = {TASK['task_id']: TASK}
    PINS = {TASK['task_id']: content_hash([TASK])}
    PROV = {'dataset_revision':'r','recurve_commit':'c','adapter_version':'v','oracle_env_hash':'o'}
    def agent(cell_, ws_):
        (Path(ws_) / 'solution.py').write_text('def task_func():\n pass\n')
        return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'single_shot',
                'tokens_in': 1, 'tokens_out': 1, 'cost_usd': 0.0}
    o = make_orchestrator(agent, TASKS, PINS, PROV)
    ws3 = Path(tempfile.mkdtemp())
    ws3.mkdir(parents=True, exist_ok=True)
    row = o({'cell_id':'x','model':'m','arm':'_AK4_PROBE_ONLY','budget':1,'seed':0,'task_id':TASK['task_id']}, ws3)
    assert row['declared_done'] is True and row['gate_outcome'] is None, row
finally:
    del A._ARMS['_AK4_PROBE_ONLY']

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=external_ci wrong: $(printf '%s' "$out"|tail -1) oracle=command is the sole authority, generic across commands, bounded by timeout"; exit 1; }
echo "DoneSignalPort['external_ci'] is a pure CLI contract: exit 0 = done, any other exit = not yet, bounded by timeout, the command alone decides — a trivial fixture and a completely different command both work with zero new Python"
exit 0
