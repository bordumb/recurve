#!/usr/bin/env bash
# TK-27: the [receipts] signer may return a JSON object, and recurve records its
# fields under the receipt's `signer_fields` — so a signer keeps its identity
# (signer_did) and a link to the verifiable envelope (envelope_ref) ON the
# receipt, not in a sidecar. Because the signer runs after self_sha256 is fixed,
# those fields are EXCLUDED from the receipt hash, so the chain still verifies. A
# bare-string return still works (backward compatible).
#
# RED-first proof, against the REAL engine on a throwaway config whose signer
# returns {"signature":"sig-<h>","signer_did":"did:test:agent","envelope_ref":...}:
#   · gate --receipts, then `receipts verify` → exit 0 (the merged fields did not
#     break the hash-chain), and the receipt carries signer_fields.signer_did.
#
# With $TRAP_FIXTURE: a fixture with the same JSON signer + a `signer-did-claim`
# file claiming the buggy value (empty — a signer whose JSON was NOT merged). The
# real engine records signer_did="did:test:agent", contradicting the empty claim →
# RED; an engine that treated the whole stdout as one opaque signature string
# would drop signer_did and agree with the bad claim.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RECURVE="$ROOT/recurve"
command -v python3 >/dev/null || { echo "python3 unavailable — cannot measure"; exit 2; }

make_project() {  # $1=dir : a suite whose signer returns a JSON object
  d="$1"; mkdir -p "$d/claims/s/probes"
  printf '#!/usr/bin/env bash\necho ok; exit 0\n' > "$d/claims/s/probes/g-1.sh"; chmod +x "$d/claims/s/probes/g-1.sh"
  printf '#!/usr/bin/env bash\nread h\nprintf '\''{"signature":"sig-%%s","signer_did":"did:test:agent","envelope_ref":"attestations/%%s.json"}'\'' "$h" "$h"\n' \
    > "$d/signer.sh"; chmod +x "$d/signer.sh"
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
    echo; echo '[receipts]'; echo 'signer = "bash signer.sh"'
    echo; echo '[suites.s]'; echo 'dir = "claims/s"'
  } > "$d/recurve.toml"
}

gate_and_verify() {  # $1=dir : gate+receipts then `receipts verify`; echo the verify exit code
  ( cd "$1"
    python3 "$RECURVE" --config recurve.toml matrix --gate --receipts >/dev/null 2>&1
    python3 "$RECURVE" --config recurve.toml receipts verify >/dev/null 2>&1; echo $? )
}

read_field() {  # $1=dir $2=dotted-path : echo the receipt's field (or "" if absent)
  ( cd "$1"
    python3 - "$2" <<'PY'
import json, sys
path = sys.argv[1].split(".")
rows = [json.loads(l) for l in open(".recurve/state/receipts/s.jsonl") if l.strip()]
v = rows[-1] if rows else {}
for k in path:
    v = v.get(k, "") if isinstance(v, dict) else ""
print(v)
PY
  )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/recurve.toml" ] || { echo "trap fixture has no recurve.toml"; exit 2; }
  [ -f "$TRAP_FIXTURE/signer-did-claim" ] || { echo "trap fixture has no signer-did-claim file"; exit 2; }
  claimed="$(tr -d '[:space:]' < "$TRAP_FIXTURE/signer-did-claim")"
  W="$(mktemp -d)"; cp -R "$TRAP_FIXTURE/." "$W/w"; rm -f "$W/w/signer-did-claim"
  gate_and_verify "$W/w" >/dev/null
  actual="$(read_field "$W/w" signer_fields.signer_did)"; rm -rf "$W"
  if [ "$actual" = "did:test:agent" ] && [ "$claimed" = "did:test:agent" ]; then
    echo "the signer's JSON return is recorded: signer_fields.signer_did landed on the receipt"
    exit 0
  fi
  if [ "$actual" != "did:test:agent" ] && [ "$claimed" != "did:test:agent" ]; then
    echo "ours=engine did not record the signer's JSON (signer_did='$actual') oracle=record the returned object"
    exit 1
  fi
  echo "ours=fixture claims signer_did '$claimed', real engine produced '$actual' oracle=the two must agree"
  exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
make_project "$T/p"
verify_rc="$(gate_and_verify "$T/p")"
[ "$verify_rc" = "0" ] || { echo "ours=receipts verify failed (exit $verify_rc) after merging the signer's JSON oracle=the chain still verifies (signer_fields excluded from the hash)"; exit 1; }

sd="$(read_field "$T/p" signer_fields.signer_did)"
er="$(read_field "$T/p" signer_fields.envelope_ref)"
sig="$(read_field "$T/p" signature)"
self="$(read_field "$T/p" self_sha256)"
[ "$sd" = "did:test:agent" ] || { echo "ours=signer_did not recorded on the receipt (got '$sd') oracle=did:test:agent"; exit 1; }
[ -n "$er" ] || { echo "ours=envelope_ref not recorded on the receipt oracle=the signer's link is persisted"; exit 1; }
case "$sig" in sig-*) : ;; *) echo "ours=signature missing/wrong after JSON merge (got '$sig') oracle=sig-<hash>"; exit 1 ;; esac
case "$self" in ????????????????????????????????????????????????????????????????) : ;; *) echo "ours=self_sha256 not a 64-hex chain hash (got '$self') oracle=the chain field is intact"; exit 1 ;; esac

# Backward compatibility: a bare-string signer still signs, and the chain verifies.
d2="$T/q"; make_project "$d2"
printf '#!/usr/bin/env bash\nread h\nprintf "sig-%%s" "$h"\n' > "$d2/signer.sh"; chmod +x "$d2/signer.sh"
legacy_rc="$(gate_and_verify "$d2")"
[ "$legacy_rc" = "0" ] || { echo "ours=receipts verify failed for a bare-string signer (exit $legacy_rc) oracle=backward compatible"; exit 1; }
legacy_sig="$(read_field "$d2" signature)"
case "$legacy_sig" in sig-*) : ;; *) echo "ours=a bare-string signer no longer sets the signature (got '$legacy_sig') oracle=backward compatible"; exit 1 ;; esac

echo "the [receipts] signer may return a JSON object (signer_fields recorded, excluded from the hash so the chain verifies); a bare-string signer still works"
exit 0
