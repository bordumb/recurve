#!/usr/bin/env bash
# TK-40: verdict invariance, measured (F2.2) — `recurve drill --iso` runs each
# iso-capable closed claim's probe once per variant with ISO_FIXTURE set. A
# form-insensitive probe's verdict holds (0 flips); a probe that keys on
# surface form (an exact spelling an isomorphic rewrite changes) flips —
# reported per probe as "iso flips f/n", failing the drill when any probe's
# flip rate exceeds the threshold.
#
# RED-first proof, against the REAL engine on throwaway projects:
#   · invariant project: probe ignores ISO_FIXTURE entirely -> flips 0/n, exit 0
#   · flipping project:  probe keys on one exact filename an iso rewrite renames
#     -> flips n/n, exit 1
#
# With $TRAP_FIXTURE: `claims` asserts drill --iso exits 0 on the flipping
# project. The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_invariant() {  # $1=dir — probe ignores ISO_FIXTURE -> verdict never flips
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
exit 0
SH
  toy_iso_gen "$1" g-1 <<'SH'
#!/bin/sh
n="${ISO_N:-4}"; i=0
while [ "$i" -lt "$n" ]; do
  mkdir -p "$ISO_OUT/v$i"; echo "same meaning, reworded $i" > "$ISO_OUT/v$i/marker"; i=$((i+1))
done
SH
}

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
  ( cd "$W/p" && python3 "$RECURVE" drill --iso >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    1) exit 1 ;;   # drill --iso fails on the flipping probe (real, correct behavior)
    0) echo "drill --iso exits 0 despite the flipping probe (fixture claimed it passes)"; exit 0 ;;
    *) echo "drill --iso errored (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

build_invariant "$T/a"
OUT="$(cd "$T/a" && python3 "$RECURVE" drill --iso 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "ours=drill --iso rc=$rc on a form-insensitive probe oracle=exit 0, 0 flips"; exit 1; }
printf '%s' "$OUT" | grep -qE "G-1 iso flips 0/" \
  || { echo "ours=no zero-flip report for g-1 oracle=drill --iso prints iso flips 0/n"; exit 1; }

build_flipping "$T/b"
OUT="$(cd "$T/b" && python3 "$RECURVE" drill --iso 2>&1)"; rc=$?
[ $rc -ne 0 ] || { echo "ours=drill --iso exit 0 with a flipping probe oracle=nonzero exit when flip rate exceeds threshold"; exit 1; }
printf '%s' "$OUT" | grep -qE "G-2 iso flips [1-9][0-9]*/" \
  || { echo "ours=flip not reported as nonzero count oracle=iso flips k/n with k>0 for the flipping probe"; exit 1; }

echo "drill --iso measures verdict invariance: form-insensitive 0/n green, surface-keyed probe flips and fails the drill"
exit 0
