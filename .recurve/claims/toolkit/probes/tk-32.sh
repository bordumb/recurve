#!/usr/bin/env bash
# TK-32: `recurve trajectories` exports the run-log as a training-ready dataset:
# one JSON object per cycle record on stdout, each row joining the record with
# its gap's ledger entry and carrying the reward and its PROVENANCE (which probe
# decided it, how many trap fixtures back it). A trajectory corpus without
# reward provenance cannot be audited; this is the export shape the
# contamination gate (TK-33) then filters.
#
# With $TRAP_FIXTURE: `claims` asserts a parked cycle exports reward=1. The
# correct engine contradicts it (reward 0 for anything not closed) -> RED.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — closed g-1 (record closed@1), open g-3 (record parked@2)
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$1" g-3 yes <<'SH'
#!/bin/sh
exit 1
SH
  # g-3 is open in the ledger (records say parked): flip the status line
  python3 - "$1/claims/s/gaps.yaml" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text().split("- id: G-3")
t[1] = t[1].replace("status: closed", "status: open", 1)
p.write_text("- id: G-3".join(t))
PY
  toy_record "$1" G-1 closed 1 run-a cycle-1
  toy_record "$1" G-3 parked 2 run-a cycle-2
}

run_export() {  # $1=projdir $2=extra flags -> stdout rows only
  ( cd "$1" && python3 "$RECURVE" trajectories $2 2>/dev/null )
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ROWS="$(run_export "$W/p" "--include-unverified")" || { echo "trajectories errored"; exit 2; }
  R="$(printf '%s\n' "$ROWS" | python3 -c '
import json,sys
for line in sys.stdin:
    if not line.strip(): continue
    d=json.loads(line)
    if d.get("gap")=="G-3": print(d.get("reward")); break
')"
  case "$R" in
    0) echo "parked cycle exports reward=0 (fixture claimed reward=1)"; exit 1 ;;
    1) exit 0 ;;   # engine pays reward for un-closed work — the dataset poisons
    *) echo "no G-3 row found — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"
ROWS="$(run_export "$T/a" "--include-unverified")"; rc=$?
if [ $rc -ne 0 ] || [ -z "$ROWS" ]; then
  echo "ours=recurve trajectories rc=$rc, no rows oracle=one JSON object per cycle record on stdout"
  exit 1
fi
printf '%s\n' "$ROWS" | python3 -c '
import json, sys
rows = [json.loads(l) for l in sys.stdin if l.strip()]
need = {"gap","suite","action","attempts","reward","files_touched","severity","provenance","verified"}
ok = (len(rows) == 2
      and all(need <= set(r) and "probe" in r["provenance"] and "traps" in r["provenance"] for r in rows))
by = {r["gap"]: r for r in rows}
ok = ok and by["G-1"]["reward"] == 1 and by["G-3"]["reward"] == 0 \
        and by["G-1"]["provenance"]["probe"].endswith("probes/g-1.sh") \
        and by["G-1"]["provenance"]["traps"] >= 1 and by["G-3"]["action"] == "parked"
sys.exit(0 if ok else 1)
' || { echo "ours=export rows malformed oracle=provenance-bearing rows, reward 1 iff closed"; exit 1; }

echo "trajectories exports one provenance-bearing JSON row per cycle record (reward 1 iff closed)"
exit 0
