#!/usr/bin/env bash
# TK-30: `recurve drill --fuzz` measures each fuzz-capable probe's false-positive
# rate against GENERATED known-bads and fails the drill when a probe blesses one.
# A probe can pass its one curated trap and still be leaky; the fuzz pass is the
# measurement that catches the leak (the verifier-fuzzing discipline, applied to
# the gate's own checks).
#
# RED-first proof, against the REAL engine on throwaway projects:
#   · strict project: probe rejects every generated variant  -> fpr 0, exit 0
#   · leaky project:  probe GREENs generated variants        -> fpr > 0, exit 1
#
# With $TRAP_FIXTURE: `claims` asserts drill --fuzz exits 0 on the leaky
# project. The correct engine contradicts it (RED); an engine that blesses the
# leak agrees with it (GREEN -> the drill screams).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_strict() {  # $1=dir — probe rejects ANY fixture; generator emits variants
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
exit 0
SH
  toy_fuzz_gen "$1" g-1 <<'SH'
#!/bin/sh
n="${FUZZ_N:-4}"; i=0
while [ "$i" -lt "$n" ]; do
  mkdir -p "$FUZZ_OUT/v$i"; echo "generated bad $i" > "$FUZZ_OUT/v$i/marker"; i=$((i+1))
done
SH
}

build_leaky() {  # $1=dir — probe rejects only the CURATED trap, GREENs variants
  toy_init "$1"
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/curated" ] && exit 1
  exit 0
fi
exit 0
SH
  toy_fuzz_gen "$1" g-2 <<'SH'
#!/bin/sh
n="${FUZZ_N:-4}"; i=0
while [ "$i" -lt "$n" ]; do
  mkdir -p "$FUZZ_OUT/v$i"; echo "generated bad $i" > "$FUZZ_OUT/v$i/marker"; i=$((i+1))
done
SH
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_leaky "$W/p"
  ( cd "$W/p" && python3 "$RECURVE" drill --fuzz >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    1) echo "leaky probe fails drill --fuzz (fixture claimed it passes)"; exit 1 ;;
    0) exit 0 ;;   # engine blessed the leak — the guard would miss its defect
    *) echo "drill --fuzz errored (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# strict project: fuzz pass must measure fpr 0 and stay green.
build_strict "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill --fuzz 2>&1)"; rc=$?
if [ $rc -ne 0 ]; then
  echo "ours=drill --fuzz rc=$rc on a strict probe ($(printf '%s' "$OUT" | grep -iE 'unrecognized|error' | head -1 | cut -c1-80)) oracle=exit 0, fpr 0"
  exit 1
fi
printf '%s' "$OUT" | grep -q "g-1" && printf '%s' "$OUT" | grep -qE "fpr[ =]0/" \
  || { echo "ours=no per-probe fpr report for g-1 oracle=drill --fuzz prints measured fpr per fuzz-capable probe"; exit 1; }

# leaky project: a generated known-bad is blessed -> nonzero fpr, drill fails.
build_leaky "$T/b"
OUT="$(cd "$T/b" && python3 "$RECURVE" drill --fuzz 2>&1)"; rc=$?
[ $rc -ne 0 ] || { echo "ours=drill --fuzz exit 0 with a leaky probe oracle=nonzero exit when fpr exceeds threshold"; exit 1; }
printf '%s' "$OUT" | grep -q "g-2" && printf '%s' "$OUT" | grep -qE "fpr[ =][1-9][0-9]*/" \
  || { echo "ours=leak not reported as nonzero fpr oracle=fpr k/n with k>0 for the leaky probe"; exit 1; }

echo "drill --fuzz measures per-probe fpr from generated known-bads: strict 0/n green, leaky k/n fails the drill"
exit 0
