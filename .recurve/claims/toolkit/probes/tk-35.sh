#!/usr/bin/env bash
# TK-35: budget-attached close rates. Raw close% inflates under retries
# (attempt inflation — the RLVR measurement critique, applied to our own
# dataset). `recurve stats` must also report close%@1 and close%@2: the share
# of cycles closed within an attempt budget, computed per class.
#
# Fixture arithmetic (class missing-surface): 4 cycles — closed@1, closed@1,
# closed@3, parked -> close% 75, close%@1 50, close%@2 50.
#
# With $TRAP_FIXTURE: `claims` asserts close%@1 equals raw close% (75%) on this
# fixture — i.e. the budget is ignored. The correct engine says 50% (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_record "$1" G-1 closed 1 run-a c1
  toy_record "$1" G-1 closed 1 run-a c2
  toy_record "$1" G-1 closed 3 run-a c3
  toy_record "$1" G-1 parked 2 run-a c4
}

stats_field() {  # $1=projdir $2=python-expr over the missing-surface row -> prints value
  ( cd "$1" && python3 "$RECURVE" stats 2>/dev/null )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  OUT="$(stats_field "$W/p")" || { echo "stats errored"; exit 2; }
  ROW="$(printf '%s\n' "$OUT" | grep '^missing-surface')" || { echo "no class row"; exit 2; }
  # budgeted column present and equal to the raw 75%? then the budget is ignored.
  if printf '%s' "$ROW" | grep -qE "75%.*75%"; then
    exit 0   # close%@1 == raw close% on a fixture where they must differ
  fi
  printf '%s' "$ROW" | grep -qE "50%" \
    && { echo "close%@1 is 50%, not the raw 75% (fixture claimed the budget is ignored)"; exit 1; }
  echo "budgeted column not found in class row"; exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"
OUT="$(stats_field "$T/a")"; rc=$?
[ $rc -eq 0 ] || { echo "ours=stats rc=$rc oracle=exit 0"; exit 1; }
printf '%s\n' "$OUT" | grep -qE "c%@1|close%@1|@1" \
  || { echo "ours=no attempt-budget column in stats header oracle=close%@1 and close%@2 reported per class"; exit 1; }
ROW="$(printf '%s\n' "$OUT" | grep '^missing-surface')"
# raw 75%, budgeted both 50% — all three must appear on the class row.
printf '%s' "$ROW" | grep -qE "75%" || { echo "ours=raw close% wrong ($ROW) oracle=75%"; exit 1; }
N50="$(printf '%s' "$ROW" | grep -oE "50%" | wc -l | tr -d ' ')"
[ "$N50" -ge 2 ] || { echo "ours=budgeted rates wrong ($ROW) oracle=close%@1 50% and close%@2 50%"; exit 1; }

echo "stats reports budget-attached close rates: raw 75% alongside close%@1 50% and close%@2 50%"
exit 0
