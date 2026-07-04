#!/usr/bin/env bash
# TK-25: `recurve receipts verify` checks each receipt's signature against the
# configured [receipts] verifier (the dual of the signer), so a tampered
# signature is caught — not only a broken hash-chain. A config with no verifier
# checks the chain as before.
#
# RED-first proof, against the REAL engine on a throwaway config with a
# signer/verifier pair (sig = "sig-<self_sha256>"):
#   · gate --receipts signs each receipt; `receipts verify` exits 0
#   · flip one receipt's signature; `receipts verify` MUST exit non-zero
#
# With $TRAP_FIXTURE: a fixture with the same pair + a `tampered-verify-exit` file
# claiming the buggy exit (0). A correct engine catches the tampered signature and
# exits non-zero, contradicting the claimed 0 → RED; an engine that only checks
# the chain would exit 0 and agree with the bad claim.
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

make_project() {
  d="$1"; mkdir -p "$d/claims/s/probes"
  printf '#!/usr/bin/env bash\necho ok; exit 0\n' > "$d/claims/s/probes/g-1.sh"; chmod +x "$d/claims/s/probes/g-1.sh"
  printf '#!/usr/bin/env bash\nread h; printf "sig-%%s" "$h"\n' > "$d/signer.sh"; chmod +x "$d/signer.sh"
  printf '#!/usr/bin/env bash\nread h; [ "$1" = "sig-$h" ]\n' > "$d/verifier.sh"; chmod +x "$d/verifier.sh"
  cat > "$d/claims/s/gaps.yaml" <<'YAML'
- id: G-1
  title: green by construction
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  covers: [G-1]
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/g-1.sh
  trap_waiver: fixture
YAML
  printf '## G-1 — green by construction\n' > "$d/claims/s/GAPS.md"
  {
    echo '[project]'; echo 'name = "fixture"'; echo 'label = "suite"'
    echo 'default_reads = "none"'; echo 'cycles_dir = "claims/s/cycles"'; echo 'schema = "1"'
    echo; echo '[target]'; echo 'tree = "."'
    echo; echo '[gate]'; echo 'traps = "off"'; echo 'quality = "pre-launch"'
    echo; echo '[reads.none]'; echo 'method = "none"'
    echo; echo '[receipts]'; echo 'signer = "bash signer.sh"'; echo 'verifier = "bash verifier.sh"'
    echo; echo '[suites.s]'; echo 'dir = "claims/s"'
  } > "$d/recurve.toml"
}

tamper_then_verify() {  # in $1: gate+receipts, flip one signature, echo the verify exit
  ( cd "$1"
    python3 "$RECURVE" --config recurve.toml matrix --gate --receipts >/dev/null 2>&1
    python3 - <<'PY'
import re
p = ".recurve/state/receipts/s.jsonl"
s = open(p).read()
open(p, "w").write(re.sub(r'"signature": "sig-[0-9a-f]+"', '"signature": "sig-FORGED"', s, count=1))
PY
    python3 "$RECURVE" --config recurve.toml receipts verify >/dev/null 2>&1; echo $? )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/recurve.toml" ] || { echo "trap fixture has no recurve.toml"; exit 2; }
  [ -f "$TRAP_FIXTURE/tampered-verify-exit" ] || { echo "trap fixture has no tampered-verify-exit file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$TRAP_FIXTURE/tampered-verify-exit")"
  W="$(mktemp -d)"; cp -R "$TRAP_FIXTURE/." "$W/w"; rm -f "$W/w/tampered-verify-exit"
  actual="$(tamper_then_verify "$W/w")"; rm -rf "$W"
  if [ "$actual" = "0" ] && [ "$claimed" = "0" ]; then
    echo "ours=receipts verify passed a tampered signature (claimed=$claimed actual=$actual) oracle=a bad signature makes verify non-zero"
    exit 1
  fi
  if [ "$actual" != "0" ] && [ "$claimed" != "0" ]; then
    echo "signature verification holds: a tampered signature makes receipts verify non-zero (exit $actual)"
    exit 0
  fi
  echo "ours=fixture claims verify exit $claimed on a tampered signature, real engine returned $actual oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# 1. Genuine signatures verify → receipts verify exits 0.
make_project "$T/p"
( cd "$T/p" \
  && python3 "$RECURVE" --config recurve.toml matrix --gate --receipts >/dev/null 2>&1 \
  && python3 "$RECURVE" --config recurve.toml receipts verify >/dev/null 2>&1 ) \
  || { echo "ours=receipts verify failed on genuine signatures oracle=0 (a valid signature verifies)"; exit 1; }

# 2. A flipped signature makes receipts verify non-zero.
make_project "$T/q"
rc="$(tamper_then_verify "$T/q")"
[ "$rc" != "0" ] || { echo "ours=receipts verify exited 0 on a tampered signature oracle=non-zero (a bad signature is caught)"; exit 1; }

echo "receipts verify checks each signature against the [receipts] verifier; a tampered signature is caught"
exit 0
