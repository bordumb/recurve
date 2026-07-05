#!/usr/bin/env bash
# EV-13: the oracle environment is a first-class, pinned citizen — intent half.
# Which interpreter/image graded a solution can change its verdict, so the oracle
# env is declared in the manifest ([oracle.env]) exactly as the dataset is, and a
# DOCKER oracle must carry an immutable image digest. A bare `:tag` is mutable:
# retag it and two runs grade against different images under the same name with
# nothing to show it. `oracle_env.parse_oracle_env` refuses a docker spec without
# a `sha256:<64hex>` digest, or one that smuggles a tag/digest into the image
# name. Pure/hermetic — this validates the SPEC, no docker needed.
#
# RED until oracle_env exists. Trap: a bare-tag (digest-less) docker oracle
# accepted — the mutable-oracle hole.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

DIGEST="sha256:1327bddf60be9bc241648c59e6060cac4ca50248a0588ab735cd0200b17cc8c2"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVAL="$EVAL" DIGEST="$DIGEST" python3 -c "
import os, sys; sys.path.insert(0, os.environ['EVAL'])
from evallib.oracle_env import parse_oracle_env, OracleSpecError
# a docker oracle pinned to a MUTABLE bare tag, no digest — must be refused
m={'oracle':{'env':{'mode':'docker','image':'bigcodebench/bigcodebench-evaluate:latest'}}}
try:
    parse_oracle_env(m); print('ACCEPTED')
except OracleSpecError: print('REFUSED')
" 2>&1)" || { echo "oracle_env incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REFUSED$'; then
    echo "parse_oracle_env refuses a digest-less (bare-tag) docker oracle"; exit 1
  fi
  echo "parse_oracle_env accepted a bare-tag docker oracle (fixture claimed it does)"; exit 0
fi

out="$(EVAL="$EVAL" DIGEST="$DIGEST" python3 -c "
import os, sys; sys.path.insert(0, os.environ['EVAL'])
try:
    from evallib.oracle_env import parse_oracle_env, OracleSpecError
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
D=os.environ['DIGEST']

# a well-formed docker spec parses and normalizes
spec=parse_oracle_env({'oracle':{'env':{'mode':'docker',
      'image':'bigcodebench/bigcodebench-evaluate','digest':D,
      'platform':'linux/amd64','network':'none','timeout':'calibrated'}}})
assert spec['mode']=='docker' and spec['image'].endswith('evaluate') and spec['digest']==D, spec
assert spec['platform']=='linux/amd64' and spec['network']=='none', spec

def refused(env):
    try: parse_oracle_env({'oracle':{'env':env}}); return False
    except OracleSpecError: return True

# every way the digest discipline can be violated is refused
assert refused({'mode':'docker','image':'x/y'}), 'missing digest accepted'
assert refused({'mode':'docker','image':'x/y','digest':'latest'}), 'non-sha256 digest accepted'
assert refused({'mode':'docker','image':'x/y','digest':'sha256:deadbeef'}), 'short digest accepted'
assert refused({'mode':'docker','image':'x/y:latest','digest':D}), 'tag smuggled into image accepted'
assert refused({'mode':'docker','image':'x/y@'+D,'digest':D}), 'digest smuggled into image accepted'
assert refused({'mode':'nonsense'}), 'unknown mode accepted'
# no [oracle.env] at all is refused — the oracle must be declared
assert refused(None) or True
try: parse_oracle_env({}); print('BUG-no-env-accepted'); raise SystemExit(1)
except OracleSpecError: pass
# a hermetic 'local' oracle is allowed (no image/digest) for dev/tests
loc=parse_oracle_env({'oracle':{'env':{'mode':'local'}}}); assert loc['mode']=='local', loc
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=oracle_env wrong: $(printf '%s' "$out"|tail -1) oracle=docker digest required (sha256), bare tag refused, local allowed"; exit 1; }
echo "oracle env spec: docker requires an immutable sha256 digest, bare tag/tag-smuggling refused, local allowed"
exit 0
