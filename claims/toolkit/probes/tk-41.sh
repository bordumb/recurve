#!/usr/bin/env bash
# TK-41: the isomorphic pass is a PARAMETER, not a policy (F2.3). Off by
# default (a plain `drill` is byte-compatible with today's: no iso output, no
# iso cost); `[drill] iso_n` bounds variants per probe; `[drill] iso_flip_max`
# turns a flip from fatal into reported. Users tune strictness to their budget.
#
# With $TRAP_FIXTURE: `claims` asserts a plain `drill` (no --iso) already runs
# the generators and prints iso flips. The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_flipping() {  # $1=dir — probe keys on one exact filename; variants rename it
  toy_init "$1"
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
if [ -n "${ISO_FIXTURE:-}" ]; then
  [ -f "$ISO_FIXTURE/original_marker" ] && exit 0
  exit 1
fi
exit 0
SH
  toy_iso_gen "$1" g-2 <<'SH'
#!/bin/sh
n="${ISO_N:-4}"; i=0
while [ "$i" -lt "$n" ]; do
  mkdir -p "$ISO_OUT/v$i"; echo "same meaning, renamed" > "$ISO_OUT/v$i/renamed_marker_$i"; i=$((i+1))
done
SH
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_flipping "$W/p"
  OUT="$(cd "$W/p" && python3 "$RECURVE" drill 2>&1)"; rc=$?
  if [ $rc -eq 0 ] && ! printf '%s' "$OUT" | grep -q "iso flips"; then
    echo "plain drill ran no iso pass (fixture claimed it runs unbidden)"; exit 1
  fi
  [ $rc -eq 0 ] || { echo "plain drill errored (rc=$rc)"; exit 2; }
  exit 0   # iso flips appeared without --iso — iso ran unbidden, the knob is gone
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# 1 · off by default: plain drill = today's behavior, no iso output, exit 0.
build_flipping "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=plain drill rc=$rc on a trap-passing project oracle=iso off by default, exit 0"; exit 1; }
printf '%s' "$OUT" | grep -q "iso flips" \
  && { echo "ours=plain drill printed iso flips oracle=no iso work unless --iso is given"; exit 1; }

# 2 · iso_n bounds the variants: denominator honors the config.
build_flipping "$T/b"
toy_conf "$T/b" '
[drill]
iso_n = 2'
OUT="$(cd "$T/b" && python3 "$RECURVE" drill --iso 2>&1)" || true
printf '%s' "$OUT" | grep -qE "iso flips [0-9]+/2\b" \
  || { echo "ours=iso_n=2 not honored (no /2 denominator) oracle=[drill] iso_n bounds variants per probe"; exit 1; }

# 3 · iso_flip_max=1.0: the flip is reported, not fatal.
build_flipping "$T/c"
toy_conf "$T/c" '
[drill]
iso_flip_max = 1.0'
OUT="$(cd "$T/c" && python3 "$RECURVE" drill --iso 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=drill --iso rc=$rc with iso_flip_max=1.0 oracle=threshold makes a flip reported-not-fatal"; exit 1; }
printf '%s' "$OUT" | grep -qE "iso flips [1-9][0-9]*/" \
  || { echo "ours=flip silent under raised threshold oracle=nonzero flip count still reported"; exit 1; }

echo "isomorphic checking is parameterized: off by default, iso_n bounds variants, iso_flip_max sets the failure threshold"
exit 0
