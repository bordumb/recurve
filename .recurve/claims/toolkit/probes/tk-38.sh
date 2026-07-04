#!/usr/bin/env bash
# TK-38: an UNDECLARED SKIP still fails the drill (F1.2) — the floor F1.1 must
# not erase: a probe can never dodge the sabotage audit by reporting its
# oracle absent unless the claim declared `oracle_waiver` up front. Proven on
# a MIXED fleet — one legitimately waived SKIP beside one undeclared SKIP —
# so the floor is checked exactly where it matters: beside the debt F1.1
# excuses, not in isolation from it.
#
# RED-first proof: before F1.1, drill already fails on ANY skip, so a lone
# undeclared-SKIP probe would be trivially GREEN pre-fix. Mixing in a
# genuinely-waived SKIP makes the claim non-trivial: pre-fix, drill's summary
# never counts an "oracle-waived" debt at all (both traps just fail alike),
# so this claim is RED until F1.1+F1.2 both land.
#
# With $TRAP_FIXTURE: `claims` asserts drill exits 0 on the mixed fleet (the
# undeclared SKIP dodging the audit under cover of the other, waived, one).
# The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — g-1 SKIPs with a declared oracle_waiver (debt);
                    # g-2 SKIPs with NO oracle_waiver (must still fail drill)
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 3
exit 0
SH
  toy_oracle_waiver "$1" g-1 "external oracle absent in this toy fixture"
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 3
exit 0
SH
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ( cd "$W/p" && python3 "$RECURVE" drill >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    0) exit 0 ;;   # engine passed the mixed fleet — the undeclared SKIP dodged
    1) echo "drill fails the mixed fleet on g-2's undeclared SKIP (fixture claimed it passes)"; exit 1 ;;
    *) echo "drill errored (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill 2>&1)"; rc=$?
[ $rc -ne 0 ] || { echo "ours=drill exit 0 on a mixed fleet oracle=nonzero exit — g-2's undeclared SKIP must still fail"; exit 1; }
printf '%s' "$OUT" | grep -qiE "1 oracle-waived" \
  || { echo "ours=g-1's declared waiver not counted oracle=1 oracle-waived counterexample alongside g-2's failure"; exit 1; }
printf '%s' "$OUT" | grep -q "G-2" \
  || { echo "ours=failure does not name g-2 oracle=the undeclared-SKIP guard is named in the output"; exit 1; }

echo "an undeclared SKIP still fails the drill on a mixed fleet, beside a correctly-waived one"
exit 0
