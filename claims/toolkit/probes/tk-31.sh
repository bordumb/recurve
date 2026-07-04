#!/usr/bin/env bash
# TK-31: fuzzing is a PARAMETER, not a policy. Off by default (a plain `drill`
# is byte-compatible with today's: no fuzz output, no fuzz cost); `[drill]
# fuzz_n` bounds variants per probe; `[drill] fuzz_fpr_max` turns a leak from
# fatal into reported. Users tune strictness to their budget.
#
# With $TRAP_FIXTURE: `claims` asserts a plain `drill` (no --fuzz) already runs
# the generators and prints fpr. The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_leaky() {  # $1=dir
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
  OUT="$(cd "$W/p" && python3 "$RECURVE" drill 2>&1)"; rc=$?
  if [ $rc -eq 0 ] && ! printf '%s' "$OUT" | grep -q "fpr"; then
    echo "plain drill ran no fuzz (fixture claimed it fuzzes unbidden)"; exit 1
  fi
  [ $rc -eq 0 ] || { echo "plain drill errored (rc=$rc)"; exit 2; }
  exit 0   # fpr appeared without --fuzz — fuzzing ran unbidden, the knob is gone
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# 1 · off by default: plain drill = today's behavior, no fuzz output, exit 0.
build_leaky "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=plain drill rc=$rc on a trap-passing project oracle=fuzz off by default, exit 0"; exit 1; }
printf '%s' "$OUT" | grep -q "fpr" \
  && { echo "ours=plain drill printed fpr oracle=no fuzz work unless --fuzz is given"; exit 1; }

# 2 · fuzz_n bounds the variants: denominator honors the config.
build_leaky "$T/b"
toy_conf "$T/b" '
[drill]
fuzz_n = 2'
OUT="$(cd "$T/b" && python3 "$RECURVE" drill --fuzz 2>&1)" || true
printf '%s' "$OUT" | grep -qE "fpr[ =][0-9]+/2\b" \
  || { echo "ours=fuzz_n=2 not honored (no /2 denominator) oracle=[drill] fuzz_n bounds variants per probe"; exit 1; }

# 3 · fuzz_fpr_max=1.0: the leak is reported, not fatal.
build_leaky "$T/c"
toy_conf "$T/c" '
[drill]
fuzz_fpr_max = 1.0'
OUT="$(cd "$T/c" && python3 "$RECURVE" drill --fuzz 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=drill --fuzz rc=$rc with fuzz_fpr_max=1.0 oracle=threshold makes a leak reported-not-fatal"; exit 1; }
printf '%s' "$OUT" | grep -qE "fpr[ =][1-9][0-9]*/" \
  || { echo "ours=leak silent under raised threshold oracle=nonzero fpr still reported"; exit 1; }

echo "fuzzing is parameterized: off by default, fuzz_n bounds variants, fuzz_fpr_max sets the failure threshold"
exit 0
