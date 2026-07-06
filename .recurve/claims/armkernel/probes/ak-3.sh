#!/usr/bin/env bash
# AK-3: BoundaryPort["open"] is a real, off-by-default bypass of
# within_boundary(), reachable ONLY through the literal [gate] boundary =
# "open" key — no realistic recurve.toml permutation (typos, partial
# configs, another arm's whole config) produces it by coincidence. When it
# IS used, that fact is recorded loudly (stderr, every single check) and
# lands as an explicit field in the cell's row provenance — never silently.
#
# RED-first: before this port existed, GitWorld had no boundary= argument at
# all — the write boundary could not be turned off through any config path,
# real or accidental.
#
# With $TRAP_FIXTURE: a [gate] boundary resolver that fuzzy-matches anything
# LOOKING like "open" (case, whitespace, suffixes) instead of requiring the
# exact literal. The real requirement must catch this — only the exact
# string "open" may ever resolve to the dangerous capability.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

# The sweep: realistic-looking [gate] blocks. Exactly ONE resolves to "open";
# everything else must be "enforced" (the default) or a hard ConfigError —
# never a silent, coincidental "open".
SWEEP='
GATE_BLOCKS = [
    ("exact_open", "[gate]\nboundary = \"open\"\n", "open", None),
    ("case_mismatch", "[gate]\nboundary = \"Open\"\n", None, "ConfigError"),
    ("all_caps", "[gate]\nboundary = \"OPEN\"\n", None, "ConfigError"),
    ("suffix_typo", "[gate]\nboundary = \"opened\"\n", None, "ConfigError"),
    ("leading_space", "[gate]\nboundary = \" open\"\n", None, "ConfigError"),
    ("trailing_space", "[gate]\nboundary = \"open \"\n", None, "ConfigError"),
    ("wrong_key_open_value", "[gate]\nadversary = \"open\"\n", None, "ConfigError"),
    ("no_gate_section", "", "enforced", None),
    ("other_keys_no_boundary", "[gate]\ntraps = \"off\"\n", "enforced", None),
    ("a7_style_config", "[gate]\nadversary = \"cross_model\"\ngovernor = \"mechanical_review\"\n",
     "enforced", None),
    ("explicit_enforced", "[gate]\nboundary = \"enforced\"\n", "enforced", None),
    ("boolean_value", "[gate]\nboundary = true\n", None, "ConfigError"),
]

def build_toml(gate_block):
    return ("[project]\nname = \"x\"\n\n[target]\ntree = \".\"\n\n"
            "[suites.s]\ndir = \"s\"\n\n" + gate_block)
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_gate_boundary.py" ] || { echo "trap fixture missing broken_gate_boundary.py"; exit 2; }
  out="$(python3 -c "
import sys, tomllib
sys.path.insert(0, '$REPO')
$SWEEP
import importlib.util
spec = importlib.util.spec_from_file_location('broken_gate_boundary', '$TRAP_FIXTURE/broken_gate_boundary.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

diverged = []
for name, block, expect_ok, expect_err in GATE_BLOCKS:
    doc = tomllib.loads(build_toml(block))
    gate = doc.get('gate', {})
    result = mod.broken_gate_boundary(gate)
    if expect_err is not None:
        # the real loader raises here; the broken resolver never raises —
        # divergence is 'produced something instead of failing loud'.
        if result == 'open':
            diverged.append(name)
    else:
        if result != expect_ok:
            diverged.append(name)
print('DIVERGED' if diverged else 'CLEAN', ','.join(diverged))
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    CLEAN*)
      echo "ours=the fuzzy resolver never diverged from strict correctness "\
           "oracle=must diverge on at least one typo/case variant — fixture failed to exercise the bug"
      exit 0 ;;
    DIVERGED*)
      echo "ours=the fuzzy resolver resolved a non-exact value to 'open' or otherwise diverged "\
           "($out) oracle=only the exact literal may ever resolve to open — correctly caught"
      exit 1 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(python3 -c "
import sys, tempfile, io, contextlib
from pathlib import Path
sys.path.insert(0, '$REPO')
sys.path.insert(0, '$EVAL')
try:
    from recurvelib.loop.adapters import GitWorld, BoundaryViolation
    from recurvelib.loop.controller import Progress
    from recurvelib.core.config import load as load_config, ConfigError
    from evallib.arms import arm_spec
    from evallib.plan import resolved_gate_config
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. the default (no boundary= at all) is byte-identical to the old,
# always-enforced GitWorld: a referee-surface write is refused.
with tempfile.TemporaryDirectory() as d:
    r = Path(d)
    (r / 'claims').mkdir()
    (r / 'claims' / 'probe.sh').write_text('guard')
    w = GitWorld(r, ['claims/'], lambda x: Progress(0, 0, 0, 0))
    assert w.boundary == 'enforced', w.boundary
    stderr = io.StringIO()
    refused = False
    with contextlib.redirect_stderr(stderr):
        try:
            w.apply({'claims/probe.sh': 'HACKED'})
        except BoundaryViolation:
            refused = True
    assert refused, 'default GitWorld did not refuse a referee-surface write'
    assert (r / 'claims' / 'probe.sh').read_text() == 'guard', 'referee surface was written despite refusal'
    assert stderr.getvalue() == '', f'enforced boundary printed something: {stderr.getvalue()!r}'

# 2. boundary='open' is REAL: the referee surface write actually succeeds —
# and it is LOUD, every single call, on stderr.
with tempfile.TemporaryDirectory() as d:
    r = Path(d)
    (r / 'claims').mkdir()
    (r / 'claims' / 'probe.sh').write_text('guard')
    w = GitWorld(r, ['claims/'], lambda x: Progress(0, 0, 0, 0), boundary='open')
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        w.apply({'claims/probe.sh': 'HACKED'})   # must NOT raise under boundary=open
    assert (r / 'claims' / 'probe.sh').read_text() == 'HACKED', 'boundary=open did not actually bypass the check'
    assert 'BOUNDARY OPEN' in stderr.getvalue(), f'boundary=open was not loud: {stderr.getvalue()!r}'

# 3. an unknown boundary value fails loud at construction, before any apply.
try:
    GitWorld(Path(tempfile.mkdtemp()), [], lambda x: Progress(0,0,0,0), boundary='not-a-real-value')
    raise SystemExit('an unknown boundary value was accepted')
except Exception as e:
    assert type(e).__name__ != 'SystemExit', str(e)

# 4. recurve.toml: [gate] boundary is enforced by default, and STRICTLY
# validated — the sweep, run through the REAL loader.
$SWEEP
for name, block, expect_ok, expect_err in GATE_BLOCKS:
    d = Path(tempfile.mkdtemp())
    (d / 's').mkdir()
    (d / 'recurve.toml').write_text(build_toml(block))
    if expect_err:
        try:
            load_config(d / 'recurve.toml')
            raise AssertionError(f'{name}: expected ConfigError, got no error')
        except ConfigError:
            pass
    else:
        cfg = load_config(d / 'recurve.toml')
        assert cfg.gate_boundary == expect_ok, f'{name}: expected {expect_ok!r}, got {cfg.gate_boundary!r}'

# 5. A5 = A3 + boundary=open; resolved_gate_config records it — and ONLY it,
# A3 stays exactly {} (unaffected by boundary= joining adversary=/governor=).
a5 = arm_spec('A5')
assert a5.workspace == 'recurve_init' and a5.done_signal == 'gate', a5
assert a5.boundary == 'open', a5
assert resolved_gate_config('A5') == {'boundary': 'open'}, resolved_gate_config('A5')
assert resolved_gate_config('A3') == {}, resolved_gate_config('A3')

# 6. end to end through the real orchestrator: A5's row records boundary=open
# LOUDLY (stderr) and explicitly (the row field); A3's row carries neither.
from evallib.orchestrate import make_orchestrator
from evallib.materialize import materialize
from evallib.taskstore import content_hash
TASK = {'task_id': 't/add', 'instruct_prompt': 'x', 'test': ''}
TASKS = {TASK['task_id']: TASK}
PINS = {TASK['task_id']: content_hash([TASK])}
PROV = {'dataset_revision':'r','recurve_commit':'c','adapter_version':'v','oracle_env_hash':'o'}
def agent(cell_, ws_):
    (Path(ws_) / 'solution.py').write_text('def task_func():\n pass\n')
    return {'terminated': True, 'agent_exit': 0, 'stop_reason': 'gate_green',
            'tokens_in': 1, 'tokens_out': 1, 'cost_usd': 0.0}
def gate_fn(ws): return 'green'
def cell(arm): return {'cell_id':'x','model':'m','arm':arm,'budget':1,'seed':0,'task_id':TASK['task_id']}

ws5 = Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A5', ws5, recurve_cmd='$REPO/recurve')
o5 = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=gate_fn)
stderr = io.StringIO()
with contextlib.redirect_stderr(stderr):
    row5 = o5(cell('A5'), ws5)
assert row5.get('boundary') == 'open', row5
assert 'BOUNDARY OPEN' in stderr.getvalue(), f'A5 cell was not loud: {stderr.getvalue()!r}'

ws3 = Path(tempfile.mkdtemp()) / 'ws'
materialize(TASK, 'A3', ws3, recurve_cmd='$REPO/recurve')
o3 = make_orchestrator(agent, TASKS, PINS, PROV, gate_fn=gate_fn)
stderr3 = io.StringIO()
with contextlib.redirect_stderr(stderr3):
    row3 = o3(cell('A3'), ws3)
assert 'boundary' not in row3, row3
assert 'BOUNDARY' not in stderr3.getvalue(), f'A3 cell was unexpectedly loud: {stderr3.getvalue()!r}'

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=BoundaryPort wrong: $(printf '%s' "$out"|tail -1) oracle=real bypass, off by default, strictly validated, loud when used"; exit 1; }
echo "BoundaryPort['open'] is a real bypass of within_boundary(), off by default, reachable ONLY through the exact [gate] boundary=\"open\" key (the sweep holds), and loud (stderr + row provenance) every time it is used — never silently"
exit 0
