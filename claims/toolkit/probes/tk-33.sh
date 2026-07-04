#!/usr/bin/env bash
# TK-33: the contamination gate. A trajectory row is VERIFIED iff its gap's
# probe exists and at least one non-waived trap fixture backs it. Unverified
# rows are EXCLUDED by default (contaminated rewards poison training data);
# `--include-unverified` re-admits them marked `"verified": false`, and the
# stderr summary reports exported-vs-excluded counts either way.
#
# With $TRAP_FIXTURE: `claims` asserts the waived gap's row exports by default.
# The correct engine contradicts it (RED); an engine that leaks unverified rows
# into the default export agrees (GREEN -> the drill screams).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — g-1 verified (trap), g-2 closed but trap_waiver
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$1" g-2 waiver <<'SH'
#!/bin/sh
exit 0
SH
  toy_record "$1" G-1 closed 1 run-a cycle-1
  toy_record "$1" G-2 closed 1 run-a cycle-2
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ROWS="$(cd "$W/p" && python3 "$RECURVE" trajectories 2>/dev/null)" || { echo "trajectories errored"; exit 2; }
  if printf '%s\n' "$ROWS" | grep -q '"gap": *"G-2"'; then
    exit 0   # unverified reward leaked into the default export
  fi
  echo "waived gap excluded from default export (fixture claimed it leaks)"; exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

OUT="$(cd "$T/a" && python3 "$RECURVE" trajectories 2>"$T/err")"; rc=$?
[ $rc -eq 0 ] || { echo "ours=trajectories rc=$rc oracle=exit 0 with a summary"; exit 1; }
printf '%s\n' "$OUT" | grep -q '"gap": *"G-1"' \
  || { echo "ours=verified row G-1 missing oracle=verified rows export by default"; exit 1; }
printf '%s\n' "$OUT" | grep -q '"gap": *"G-2"' \
  && { echo "ours=unverified G-2 exported by default oracle=waived-trap rewards are excluded"; exit 1; }
grep -qE "excluded 1" "$T/err" \
  || { echo "ours=no excluded-count summary oracle=stderr reports exported vs excluded"; exit 1; }

OUT2="$(cd "$T/a" && python3 "$RECURVE" trajectories --include-unverified 2>/dev/null)"
printf '%s\n' "$OUT2" | python3 -c '
import json, sys
rows = {r["gap"]: r for r in (json.loads(l) for l in sys.stdin if l.strip())}
sys.exit(0 if rows.get("G-2",{}).get("verified") is False
           and rows.get("G-1",{}).get("verified") is True else 1)
' || { echo "ours=--include-unverified rows not marked oracle=G-2 verified:false, G-1 verified:true"; exit 1; }

echo "contamination gate holds: unverified rewards excluded by default, marked when re-admitted, counts summarized"
exit 0
