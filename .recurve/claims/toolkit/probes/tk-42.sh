#!/usr/bin/env bash
# TK-42: reference oracles / differential probes (F2.4) — a claim may declare
# `reference: probes/<id>.ref.sh`, a stricter or slower check of the same
# proposition. `recurve drill --diff` runs both the probe and its reference
# against the true state; disagreement (one GREEN, the other RED) is an
# alarm that fails the drill, naming both verdicts; agreeing checks pass;
# without --diff the drill is unchanged. The field survives the baseline
# promotion ceremony.
#
# RED-first proof, against the REAL engine on throwaway projects:
#   · g-1: probe and reference agree GREEN -> drill --diff passes for g-1
#   · g-2: probe GREEN, reference RED -> drill --diff exits 1, naming g-2
#   · a draft carrying `reference` keeps it after `recurve baseline`
#
# With $TRAP_FIXTURE: `claims` asserts drill --diff exits 0 despite g-2's
# probe/reference disagreement. The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — g-1 probe+reference agree GREEN; g-2 probe GREEN, reference RED
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
exit 0
SH
  toy_ref_probe "$1" g-1 <<'SH'
#!/bin/sh
exit 0
SH
  toy_reference "$1" g-1 g-1.ref.sh
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
exit 0
SH
  toy_ref_probe "$1" g-2 <<'SH'
#!/bin/sh
exit 1
SH
  toy_reference "$1" g-2 g-2.ref.sh
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ( cd "$W/p" && python3 "$RECURVE" drill --diff >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    1) exit 1 ;;   # drill --diff fails on g-2's disagreement (real, correct behavior)
    0) echo "drill --diff exits 0 despite g-2's probe/reference disagreement (fixture claimed it passes)"; exit 0 ;;
    *) echo "drill --diff errored (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

OUT="$(cd "$T/a" && python3 "$RECURVE" drill --diff 2>&1)"; rc=$?
[ $rc -ne 0 ] || { echo "ours=drill --diff exit 0 despite g-2's disagreement oracle=nonzero exit on any probe/reference disagreement"; exit 1; }
printf '%s' "$OUT" | grep -q "G-1" && printf '%s' "$OUT" | grep "G-1" | grep -qv "DISAGREEMENT" \
  || { echo "ours=g-1 (agreeing) reported as a disagreement oracle=agreeing checks pass"; exit 1; }
printf '%s' "$OUT" | grep "G-2" | grep -q "DISAGREEMENT" \
  || { echo "ours=g-2's disagreement not named oracle=a disagreement line naming both verdicts"; exit 1; }

OUT2="$(cd "$T/a" && python3 "$RECURVE" drill 2>&1)"; rc2=$?
[ $rc2 -eq 0 ] || { echo "ours=plain drill rc=$rc2 with an undeclared --diff oracle=unchanged, exit 0"; exit 1; }
printf '%s' "$OUT2" | grep -q "diff:" \
  && { echo "ours=plain drill ran the diff pass oracle=no reference work unless --diff is given"; exit 1; }

# the reference field must survive the baseline promotion ceremony
toy_init "$T/c"
cat > "$T/c/claims/s/probes/g-9.sh" <<'SH'
#!/bin/sh
exit 1
SH
chmod +x "$T/c/claims/s/probes/g-9.sh"
cat > "$T/c/claims/s/probes/g-9.ref.sh" <<'SH'
#!/bin/sh
exit 1
SH
chmod +x "$T/c/claims/s/probes/g-9.ref.sh"
cat > "$T/c/claims/s/gaps.draft.yaml" <<'YAML'
- id: G-9
  title: toy draft with a reference oracle
  class: missing-surface
  severity: feature
  reads: none
  covers: ["G-9"]
  evidence: ["x:1"]
  smallest_fix: none
  probe: probes/g-9.sh
  reference: probes/g-9.ref.sh
YAML
( cd "$T/c" && python3 "$RECURVE" baseline s >/dev/null 2>&1 )
grep -q "reference: probes/g-9.ref.sh" "$T/c/claims/s/gaps.yaml" \
  || { echo "ours=reference dropped by baseline promotion oracle=a draft carrying reference keeps it on promotion"; exit 1; }

echo "drill --diff alarms on probe/reference disagreement, passes on agreement, and the reference field survives baseline"
exit 0
