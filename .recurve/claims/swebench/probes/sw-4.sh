#!/usr/bin/env bash
# SW-4: calibration against the canonical patch, keyed per environment image.
# `calibration.py`'s derive_calibration/calibration_admits_spend are reused
# completely UNCHANGED (SW4's whole point). What's new: the calibration
# artifact is keyed by the FULL `environment_image_hash` (instance identity +
# image digest), not one global hash or the digest alone — a SWE-bench
# sample spans many distinct environments.
#
# RED-first: before evallib/swebench_calibration.py existed, there was no
# per-environment keying at all — `eval/calibrations/*.json`'s existing
# convention is keyed by a single global oracle_env_hash (BigCodeBench has
# exactly one oracle for the whole run).
#
# With $TRAP_FIXTURE: a keying function that uses the docker DIGEST alone,
# dropping instance identity — two different instances sharing a base/env
# image layer collapse onto the SAME calibration file.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIXTURES='
LOCK_A = {"instance_id": "pallets__flask-5014", "repo": "pallets/flask",
          "base_commit": "aaa", "digest": "sha256:shared0000", "platform": "linux/x86_64", "host": "h"}
LOCK_B = {"instance_id": "psf__requests-5414", "repo": "psf/requests",
          "base_commit": "bbb", "digest": "sha256:shared0000", "platform": "linux/x86_64", "host": "h"}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_calibration_path.py" ] || { echo "trap fixture missing broken_calibration_path.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
import importlib.util
spec = importlib.util.spec_from_file_location('broken_calibration_path', '$TRAP_FIXTURE/broken_calibration_path.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pa = mod.calibration_path_for_environment('/repo', LOCK_A)
pb = mod.calibration_path_for_environment('/repo', LOCK_B)
print('COLLIDED' if pa == pb else 'DISTINCT')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    COLLIDED)
      echo "ours=digest-only keying collapsed two different instances onto one "\
           "calibration file oracle=must key by full instance identity — correctly caught the collision"
      exit 1 ;;
    DISTINCT)
      echo "ours=broken_calibration_path unexpectedly kept them distinct "\
           "oracle=the fixture failed to exercise the digest-only collision"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
try:
    from evallib.swebench_calibration import (
        calibration_path_for_environment, derive_calibration, calibration_admits_spend,
        exclusion_content_hash, CalibrationError,
    )
    from evallib.swebench_env import environment_image_hash
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. two instances sharing a digest but differing instance_id/base_commit ->
# DIFFERENT environment_image_hash -> DIFFERENT calibration paths.
ha, hb = environment_image_hash(LOCK_A), environment_image_hash(LOCK_B)
assert ha != hb, (ha, hb)
pa = calibration_path_for_environment('/repo', ha)
pb = calibration_path_for_environment('/repo', hb)
assert pa != pb, (pa, pb)

# 2. derive_calibration/calibration_admits_spend are the SAME functions
# calibration.py already gates (EV-16) -- reused, not reimplemented.
results = {'pallets__flask-5014': {'verdict': 'pass', 'seconds': 3.1}}
cal = derive_calibration(ha, 'dsh:1', results, {})
assert cal['raw_pass_rate'] == 1.0, cal
calibration_admits_spend(cal, oracle_env_hash=ha, dataset_hash='dsh:1', exclusions_content={})
try:
    calibration_admits_spend(cal, oracle_env_hash=hb, dataset_hash='dsh:1', exclusions_content={})
    raise AssertionError('a different environment silently admitted spend')
except CalibrationError:
    pass

# 3. an unexplained canonical failure still refuses (EV-16's teeth, untouched).
bad_results = {'pallets__flask-5014': {'verdict': 'fail', 'seconds': 1.0}}
try:
    derive_calibration(ha, 'dsh:1', bad_results, {})
    raise AssertionError('unexplained failing canonical was NOT refused')
except CalibrationError:
    pass

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW4 calibration keying wrong: $(printf '%s' "$out"|tail -1) oracle=calibration keyed by full per-instance environment_image_hash, teeth reused unchanged"; exit 1; }
echo "calibration keyed by full environment_image_hash (instance identity + digest, never digest alone); derive_calibration/calibration_admits_spend reused unchanged from the eval suite's own EV-16"
exit 0
