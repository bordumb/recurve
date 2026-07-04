#!/usr/bin/env bash
# TK-36: verification debt is visible where the rates are read. A closed gap
# with `trap_waiver` is a guard the drill cannot audit; `recurve stats` must
# print that debt (`trap debt: N waived guard(s)`) next to the close rates it
# qualifies, so a green-looking dataset cannot hide unaudited guards.
#
# With $TRAP_FIXTURE: `claims` asserts stats reports zero trap debt on a
# fixture holding one waived guard. The correct engine reports 1 (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — g-1 closed+trap (no debt), g-2 closed+waiver (debt 1)
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$1" g-2 waiver <<'SH'
#!/bin/sh
exit 0
SH
  toy_record "$1" G-1 closed 1 run-a c1
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  OUT="$(cd "$W/p" && python3 "$RECURVE" stats 2>/dev/null)" || { echo "stats errored"; exit 2; }
  if printf '%s\n' "$OUT" | grep -qE "trap debt: *1"; then
    echo "stats reports trap debt 1 (fixture claimed 0)"; exit 1
  fi
  printf '%s\n' "$OUT" | grep -qE "trap debt: *0" && exit 0   # debt hidden
  echo "no trap-debt line at all"; exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" stats 2>/dev/null)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=stats rc=$rc oracle=exit 0"; exit 1; }
printf '%s\n' "$OUT" | grep -qE "trap debt: *1 waived guard" \
  || { echo "ours=no trap-debt line oracle='trap debt: 1 waived guard' for one waived closed gap"; exit 1; }

echo "stats surfaces verification debt: trap debt: 1 waived guard on a one-waiver ledger"
exit 0
