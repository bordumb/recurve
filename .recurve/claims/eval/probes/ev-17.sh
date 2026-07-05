#!/usr/bin/env bash
# EV-17: the spend gate is WIRED into the paid path. EV-16 is the logic; this is
# the enforcement — `cmd_run` calls `assert_spend_admitted` FIRST, before it
# resolves a task or spawns an agent, so a run whose oracle env has no passing
# calibration costs exactly nothing. assert_spend_admitted reads the run dir's
# oracle.lock.json, finds the calibration keyed by its oracle_env_hash, and
# refuses (no calibration / different dataset / edited exclusions) or returns the
# admitting calibration with its resolved timeout. Hermetic: no docker, no agent —
# the refusal happens before either could be reached.
#
# RED until cmd_run gates on calibration. Trap: a run admitted (or reaching the
# work queue) with no calibration for its oracle env — a paid run on an
# uncalibrated, possibly-broken oracle.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys, json, tempfile, pathlib, inspect
sys.path.insert(0, os.environ["EVAL"])
from evallib.calibration import exclusion_content_hash

def make_run(oeh="oeh:ev17", dataset_hash="dh:ev17"):
    d = pathlib.Path(tempfile.mkdtemp())
    (d/"manifest.toml").write_text(
        "[matrix]\nmodels=[\"m\"]\narms=[\"A0\"]\nbudgets=[1]\nseeds=[0]\n"
        "[tasks]\nlocal=\"/nonexistent.jsonl\"\nhash=\""+dataset_hash+"\"\ncount=1\n"
        "[oracle.env]\nmode=\"local\"\n")
    (d/"oracle.lock.json").write_text(json.dumps({"mode":"local","oracle_env_hash":oeh,
        "resolved_timeout":None}))
    (d/"matrix.jsonl").write_text(json.dumps({"cell_id":"c","model":"m","arm":"A0",
        "budget":1,"seed":0,"task_id":"t"})+"\n")
    return d

def fake_repo(cal=None, oeh="oeh:ev17"):
    r = pathlib.Path(tempfile.mkdtemp())
    caldir = r/"eval"/"calibrations"; caldir.mkdir(parents=True)
    if cal is not None:
        (caldir/(oeh.replace(":","-")+".json")).write_text(json.dumps(cal))
    return r

def good_cal(oeh="oeh:ev17", dataset_hash="dh:ev17"):
    return {"oracle_env_hash":oeh,"dataset_hash":dataset_hash,"raw_pass_rate":1.0,
            "exclusions":[],"exclusion_hash":exclusion_content_hash([]),"resolved_timeout":42}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
$HELP
from evallib.cli import assert_spend_admitted
from evallib.calibration import CalibrationError
d=make_run(); r=fake_repo(cal=None)     # a run dir whose oracle env has NO calibration
try:
    assert_spend_admitted(d, r); print('ADMITTED')
except CalibrationError: print('REFUSED')
" 2>&1)" || { echo "cli incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REFUSED$'; then
    echo "assert_spend_admitted refuses a run with no calibration for its oracle env"; exit 1
  fi
  echo "assert_spend_admitted admitted an uncalibrated oracle (fixture claimed it does)"; exit 0
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    from evallib.cli import assert_spend_admitted, cmd_run, main
    from evallib.calibration import CalibrationError
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# admits only when a matching calibration exists; returns it with the calibrated timeout
d=make_run(); r=fake_repo(cal=good_cal())
cal=assert_spend_admitted(d, r); assert cal['resolved_timeout']==42, cal

def refuses(run_dir, repo):
    try: assert_spend_admitted(run_dir, repo); return False
    except CalibrationError: return True

assert refuses(make_run(), fake_repo(cal=None)), 'no calibration admitted'
assert refuses(make_run(oeh='oeh:other'), fake_repo(cal=good_cal(), oeh='oeh:ev17')), 'stale oracle-env key admitted'
# edited exclusions: the calibration on disk claims exclusions the lock check will not match
bad=good_cal(); bad['exclusions']=['sneak']       # hash no longer matches the empty-list content the loader reads? here loader reads cal's own list
# (loader passes cal['exclusions'] as content; so tamper the recorded hash instead)
bad2=good_cal(); bad2['exclusion_hash']='exh:tampered'
assert refuses(make_run(), fake_repo(cal=bad2)), 'exclusion-hash mismatch admitted'

# WIRED: cmd_run consults the gate before doing anything else
src=inspect.getsource(cmd_run)
assert 'assert_spend_admitted' in src, 'cmd_run does not call the spend gate'
# and the gate CALL precedes the adapter CALL (compare call sites, not the import line)
assert src.index('assert_spend_admitted(run_dir') < src.index('adapter = make_pipeline_adapter'), 'gate is not before the adapter'

# BEHAVIORAL: a real cmd_run over a run dir with no calibration returns nonzero and seals NOTHING
d2=make_run(oeh='oeh:ev17-nocal-'+str(abs(hash('x'))%9999))
rc=main(['run', str(d2)])
assert rc!=0, ('cmd_run did not refuse an uncalibrated run', rc)
assert not (d2/'results.jsonl').exists(), 'cmd_run sealed rows despite refusing to spend'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=spend gate not wired: $(printf '%s' "$out"|tail -1) oracle=cmd_run refuses (before tasks/agent) unless calibration admits, sealing nothing"; exit 1; }
echo "spend gate wired: cmd_run refuses (before any task or agent, sealing nothing) unless the oracle env is calibrated"
exit 0
