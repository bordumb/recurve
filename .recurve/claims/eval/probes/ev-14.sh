#!/usr/bin/env bash
# EV-14: the oracle environment resolved and locked — the resolution half. At
# plan time the declared spec (EV-13) is resolved against the machine into an
# oracle.lock.json: the image digest ACTUALLY present locally (refused if it
# disagrees with the manifest — same semantics as the dataset hash: retag the
# image and plan refuses), the platform + emulation flag, the container's Python,
# the grading-wrapper hash, and a host fingerprint. `oracle_env_hash` digests the
# VERDICT-AFFECTING identity subset only — deliberately NOT the calibration-
# derived timeout/exclusions (those are keyed BY this hash, so including them
# would be circular). Any identity change (image, platform, wrapper, python,
# host) changes the hash and so invalidates a stale calibration automatically.
# Hermetic: the docker queries are injected; the resolution/hash/drift logic is
# pure.
#
# RED until resolve_oracle_lock/oracle_env_hash exist. Traps: a locally-present
# digest that disagrees with the manifest accepted (drift not refused); the hash
# ignoring the grading-wrapper (a changed grader reading as the same oracle).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

D="sha256:1327bddf60be9bc241648c59e6060cac4ca50248a0588ab735cd0200b17cc8c2"
D2="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

HELP="
import os, sys; sys.path.insert(0, os.environ['EVAL'])
from evallib.oracle_env import parse_oracle_env, resolve_oracle_lock, oracle_env_hash, OracleDriftError
D='$D'; D2='$D2'
SPEC=parse_oracle_env({'oracle':{'env':{'mode':'docker',
     'image':'bigcodebench/bigcodebench-evaluate','digest':D,'platform':'linux/amd64','network':'none'}}})
def present(want):        # a digest_probe returning a chosen local digest
    return lambda image: want
def py(*a, **k): return 'Python 3.10.14'
"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo drift_not_refused)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='drift_not_refused':
    try:
        resolve_oracle_lock(SPEC, digest_probe=present(D2), python_probe=py, wrapper_sha='w', host='h')
        print('ACCEPTED')
    except OracleDriftError: print('REFUSED')
elif sc=='hash_ignores_wrapper':
    a=resolve_oracle_lock(SPEC, digest_probe=present(D), python_probe=py, wrapper_sha='w1', host='h')
    b=resolve_oracle_lock(SPEC, digest_probe=present(D), python_probe=py, wrapper_sha='w2', host='h')
    print('SAME' if a['oracle_env_hash']==b['oracle_env_hash'] else 'DIFFERENT')
" 2>&1)" || { echo "oracle_env incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    drift_not_refused:REFUSED)      echo "resolve_oracle_lock refuses a digest that disagrees with the manifest"; exit 1 ;;
    hash_ignores_wrapper:DIFFERENT) echo "oracle_env_hash changes when the grading wrapper changes"; exit 1 ;;
    *) echo "resolution failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# resolve a docker lock when the pinned digest IS present locally
lock=resolve_oracle_lock(SPEC, digest_probe=present(D), python_probe=py, wrapper_sha='wsha', host='host-A')
assert lock['digest']==D and lock['platform']=='linux/amd64' and lock['network']=='none', lock
assert lock['container_python']=='Python 3.10.14' and lock['wrapper_sha']=='wsha' and lock['host']=='host-A', lock
assert lock['oracle_env_hash'].startswith('oeh:'), lock
# calibration-derived fields exist but start empty (filled after calibration)
assert lock['resolved_timeout'] is None and lock['exclusion_hash'] is None, lock

# refuse-on-drift: the digest present locally disagrees with the manifest pin
try:
    resolve_oracle_lock(SPEC, digest_probe=present(D2), python_probe=py, wrapper_sha='wsha', host='host-A')
    raise SystemExit('drift not refused')
except OracleDriftError: pass
# image absent locally (probe returns None) is also drift — cannot grade
try:
    resolve_oracle_lock(SPEC, digest_probe=lambda i: None, python_probe=py, wrapper_sha='wsha', host='host-A')
    raise SystemExit('missing image not refused')
except OracleDriftError: pass

# oracle_env_hash is deterministic and identity-sensitive...
h=lock['oracle_env_hash']
assert oracle_env_hash(lock)==h, 'hash not deterministic'
def rehash(**over):
    l=dict(lock); l.update(over); return oracle_env_hash(l)
assert rehash(wrapper_sha='other')!=h, 'hash ignores wrapper'
assert rehash(container_python='Python 3.11.0')!=h, 'hash ignores container python'
assert rehash(platform='linux/arm64')!=h, 'hash ignores platform'
assert rehash(host='host-B')!=h, 'hash ignores host (emulation timing lives here)'
assert rehash(digest=D2)!=h, 'hash ignores image digest'
# ...but NOT the calibration-derived fields (else keying calibration by it is circular)
assert rehash(resolved_timeout=42)==h, 'hash must exclude the calibrated timeout'
assert rehash(exclusion_hash='xh')==h, 'hash must exclude the exclusion list'

# a hermetic 'local' oracle also resolves to a lock + hash (no image/digest)
loc=resolve_oracle_lock(parse_oracle_env({'oracle':{'env':{'mode':'local'}}}),
                        python_probe=py, wrapper_sha='', host='host-A')
assert loc['mode']=='local' and loc['oracle_env_hash'].startswith('oeh:'), loc
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=oracle_env resolution wrong: $(printf '%s' "$out"|tail -1) oracle=lock resolved, drift refused, identity hash excludes calibration-derived fields"; exit 1; }
echo "oracle env resolved to a lock; digest drift refused; oracle_env_hash is identity-sensitive and calibration-independent"
exit 0
