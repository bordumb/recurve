#!/usr/bin/env bash
# TK-37: `recurve drill` honors a declared oracle_waiver on a trap's SKIP
# outcome (F1.1) — it mirrors the gate's `is_waived_skip` semantics instead
# of failing the whole audit on a claim whose external oracle is legitimately
# absent ("a guard would bless its own defect" was the pre-fix verdict on an
# otherwise clean fleet).
#
# RED-first proof, against the REAL engine on a throwaway project:
#   · one closed claim declares oracle_waiver; its trap SKIPs (exit 3) under
#     TRAP_FIXTURE -> drill must exit 0 and count 1 oracle-waived counterexample
#
# With $TRAP_FIXTURE: `claims` asserts drill fails on the waived SKIP (the
# pre-F1.1 bug). The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — closed g-1: oracle_waiver declared, trap SKIPs
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 3
exit 0
SH
  toy_oracle_waiver "$1" g-1 "external oracle absent in this toy fixture"
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ( cd "$W/p" && python3 "$RECURVE" drill >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    0) exit 1 ;;   # drill correctly passes the waived SKIP — contradicts the "it fails" claim
    1) echo "drill fails the waived SKIP (fixture claimed the fix holds)"; exit 0 ;;
    *) echo "drill errored (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=drill rc=$rc on a waived-SKIP-only fleet oracle=exit 0, the SKIP is non-blocking debt"; exit 1; }
printf '%s' "$OUT" | grep -qiE "1 oracle-waived" \
  || { echo "ours=summary does not count the oracle-waived counterexample oracle=drill counts it beside the waived-guards figure"; exit 1; }

echo "drill honors the declared oracle_waiver: a SKIP trap is non-blocking, visible debt (1 oracle-waived)"
exit 0
