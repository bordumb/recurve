#!/usr/bin/env bash
# TK-39: the isomorphic generator convention (F2.1) — a claim may ship an
# executable probes/<id>.iso.sh. Called with ISO_OUT=<dir> ISO_N=<n>, it
# writes up to n semantics-preserving variant directories; `recurve drill
# --iso` discovers and consumes it (per closed claim, independently); a
# claim shipping no generator is untouched and reports nothing.
#
# RED-first proof, against the REAL engine on a throwaway project:
#   · g-1 ships probes/g-1.iso.sh; g-2 ships none
#   · drill --iso reports g-1, never g-2
#
# With $TRAP_FIXTURE: `claims` asserts drill --iso ignores g-1's generator
# (ships it, never consumes it). The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — g-1 ships an iso generator; g-2 ships none
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
  mkdir -p "$ISO_OUT/v$i"; echo "variant $i" > "$ISO_OUT/v$i/marker"; i=$((i+1))
done
SH
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
[ -n "${TRAP_FIXTURE:-}" ] && exit 1
exit 0
SH
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  OUT="$(cd "$W/p" && python3 "$RECURVE" drill --iso 2>&1)"
  if printf '%s' "$OUT" | grep -q "G-1 iso"; then
    exit 1   # drill --iso reports g-1's generator — contradicts "ignores it"
  fi
  echo "drill --iso ignores g-1's generator (fixture claimed it does)"; exit 0
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

GOUT="$(mktemp -d)"; trap 'rm -rf "$GOUT"' EXIT
( cd "$T/a/claims/s/probes" && ISO_OUT="$GOUT" ISO_N=3 bash g-1.iso.sh ) \
  || { echo "ours=iso generator errored oracle=writes variant dirs under ISO_OUT"; exit 1; }
N="$(find "$GOUT" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
[ "$N" -ge 1 ] && [ "$N" -le 3 ] \
  || { echo "ours=$N variant dir(s) written oracle=up to ISO_N=3 directories under ISO_OUT"; exit 1; }

OUT="$(cd "$T/a" && python3 "$RECURVE" drill --iso 2>&1)"
printf '%s' "$OUT" | grep -q "G-1 iso" \
  || { echo "ours=drill --iso does not mention g-1 oracle=the iso-capable probe is discovered and reported"; exit 1; }
printf '%s' "$OUT" | grep -q "G-2 iso" \
  && { echo "ours=drill --iso reports g-2 (ships no generator) oracle=claims without a generator are untouched"; exit 1; }

echo "drill --iso discovers probes/<id>.iso.sh generators, consumes up to ISO_N variants, leaves generator-less claims untouched"
exit 0
