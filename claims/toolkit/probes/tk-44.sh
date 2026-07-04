#!/usr/bin/env bash
# TK-44: trajectories export branches (F3.2) — `recurve trajectories` includes
# each row's `branches` (an empty array when the record has none), under the
# same provenance/contamination gating as the rest of the row, preserving the
# export's determinism.
#
# RED-first proof, against the REAL engine on a throwaway project:
#   · a record carrying two branches -> its exported row's branches match verbatim
#   · a record with none -> its exported row carries "branches": []
#   · two consecutive exports are byte-identical
#
# With $TRAP_FIXTURE: `claims` asserts the exported row for the branch-carrying
# cycle has 0 branches (dropped). The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — G-1's record carries two branches; G-2's carries none
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
exit 0
SH
  printf '{"schema_version":"1.0.0","project":"toy","run_id":"run-a","cycle":"cycle-1","gap":"G-1","suite":"s","class":"missing-surface","severity":"feature","status":"closed","attempts":1,"files_touched":["f.txt"],"net_new_gaps":0,"regressions_caught":0,"summary":"toy cycle","wall_clock_s":10,"branches":[{"kind":"attempt","description":"tried X first","rejected_because":"too slow"},{"kind":"approach","description":"considered Y","rejected_because":"lacks the infra"}]}\n' >> "$1/.recurve/state/records.jsonl"
  toy_record "$1" G-2 closed 1 run-a cycle-2
}

run_export() {  # $1=projdir -> stdout rows only
  ( cd "$1" && python3 "$RECURVE" trajectories --include-unverified 2>/dev/null )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ROWS="$(run_export "$W/p")" || { echo "trajectories errored"; exit 2; }
  R="$(printf '%s\n' "$ROWS" | python3 -c '
import json,sys
for line in sys.stdin:
    if not line.strip(): continue
    d=json.loads(line)
    if d.get("gap")=="G-1":
        print(len(d.get("branches") or [])); break
')"
  case "$R" in
    0) exit 0 ;;   # G-1 exports 0 branches — dropped, matches the wrong claim
    2) echo "G-1 exports 2 branches intact (fixture claimed they're dropped)"; exit 1 ;;
    *) echo "no G-1 row found — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

ROWS="$(run_export "$T/a")"; rc=$?
[ $rc -eq 0 ] && [ -n "$ROWS" ] || { echo "ours=trajectories rc=$rc, no rows oracle=one JSON row per cycle record"; exit 1; }
printf '%s\n' "$ROWS" | python3 -c '
import json, sys
rows = [json.loads(l) for l in sys.stdin if l.strip()]
by = {r["gap"]: r for r in rows}
ok = ("branches" in by.get("G-1", {}) and by["G-1"]["branches"] ==
      [{"kind":"attempt","description":"tried X first","rejected_because":"too slow"},
       {"kind":"approach","description":"considered Y","rejected_because":"lacks the infra"}]
      and by.get("G-2", {}).get("branches") == [])
sys.exit(0 if ok else 1)
' || { echo "ours=branches missing, wrong, or not defaulted to [] oracle=verbatim branches; [] when none"; exit 1; }

( cd "$T/a" && python3 "$RECURVE" trajectories --include-unverified >"$T/run1" 2>/dev/null )
( cd "$T/a" && python3 "$RECURVE" trajectories --include-unverified >"$T/run2" 2>/dev/null )
cmp -s "$T/run1" "$T/run2" \
  || { echo "ours=two exports of identical state differ oracle=byte-identical re-runs"; exit 1; }

echo "trajectories exports branches verbatim (empty array when none), byte-identical across re-runs"
exit 0
