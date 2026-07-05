#!/usr/bin/env bash
# EV-18 (O2b): the oracle image is derivable-from-repo, and reconciled to the pin
# — never silently rebuilt. A docker rebuild is not bit-reproducible (build-time
# downloads), so a silently adopted rebuild would quietly become the oracle and
# bypass the pin -> lock -> calibration chain. So the rebuild is an explicit verb
# (`eval oracle build`) that builds from the committed Dockerfile, reads the
# resulting image Id, and RECONCILES it against the manifest pin: match -> proceed;
# mismatch -> refuse, naming the remediation (update the pin, rebuild the lock,
# RECALIBRATE — a different image is a different oracle, its calibration stale).
# And `plan`'s refusal on a MISSING image names the one-command remediation, so a
# fresh clone reaches "ready to plan" from committed files alone. The reconcile +
# remediation logic is hermetic; the actual build is oracle-waived (docker+net).
#
# RED until oracle_build exists and plan names the remediation. Traps: a
# divergent-digest rebuild silently adopted; a missing-image refusal that does not
# name the remediation.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo silent_adopt)"
  out="$(EVAL="$EVAL" python3 -c "
import os, sys; sys.path.insert(0, os.environ['EVAL'])
from evallib.oracle_build import reconcile_digest, missing_image_remediation, OracleImageMismatch, BUILD_VERB
sc='$scenario'
if sc=='silent_adopt':
    try:
        reconcile_digest('sha256:BUILT', 'sha256:PINNED'); print('ADOPTED')
    except OracleImageMismatch: print('REFUSED')
elif sc=='no_remediation':
    msg=missing_image_remediation('recurve-bcb-oracle','sha256:abc')
    print('NAMED' if BUILD_VERB in msg else 'UNNAMED')
" 2>&1)" || { echo "oracle_build incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    silent_adopt:REFUSED)  echo "reconcile_digest refuses a divergent rebuild (no silent adopt)"; exit 1 ;;
    no_remediation:NAMED)  echo "the missing-image refusal names the build-verb remediation"; exit 1 ;;
    *) echo "oracle_build failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
import os, sys, inspect; sys.path.insert(0, os.environ['EVAL'])
try:
    from evallib.oracle_build import (reconcile_digest, missing_image_remediation,
                                      OracleImageMismatch, BUILD_VERB)
    from evallib import cli
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# a matching rebuild reconciles cleanly
assert reconcile_digest('sha256:AAA', 'sha256:AAA') == 'match'
# a divergent rebuild refuses, and the message names the remediation (re-pin + recalibrate)
try:
    reconcile_digest('sha256:BUILT', 'sha256:PINNED'); raise SystemExit('divergent build adopted')
except OracleImageMismatch as e:
    m=str(e).lower()
    assert 'sha256:built' in m and 'recalibrat' in m, ('remediation not specific', str(e))

# the missing-image refusal names the one-command remediation
rem=missing_image_remediation('recurve-bcb-oracle','sha256:697c')
assert BUILD_VERB in rem, rem

# the build verb exists and plan wires the remediation on a missing image
assert hasattr(cli, 'cmd_oracle_build'), 'no eval oracle build verb'
assert 'oracle' in inspect.getsource(cli.main) and 'build' in inspect.getsource(cli.main), 'oracle build not registered'
assert 'missing_image_remediation' in inspect.getsource(cli.cmd_plan), 'plan does not name the remediation on a missing image'

# the committed Dockerfile IS the derivation source (derivable-from-repo)
import pathlib
df=pathlib.Path(os.environ['EVAL'])/'oracle'/'Dockerfile.nltk'
assert df.exists() and 'FROM bigcodebench' in df.read_text(), 'derived-image Dockerfile not committed'
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=oracle_build wrong: $(printf '%s' "$out"|tail -1) oracle=reconcile refuses divergent rebuild, plan names remediation, Dockerfile committed"; exit 1; }
echo "oracle image is derivable-from-repo: reconcile refuses a divergent rebuild, plan names the build-verb remediation"
exit 0
