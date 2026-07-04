#!/usr/bin/env bash
# Known-bad template: the pre-wave loop. It halts the moment the strict
# ledger empties, stranding every pending draft unprobed and unbuilt.
set -u
PROG="${RECURVE_BIN:-recurve}"
CAP="${CAP:-12}"
for cycle in $(seq 1 "$CAP"); do
  GAP="$($PROG next --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["recommended"]["gap"] if d.get("recommended") else "")')"
  if [ -z "$GAP" ]; then
    echo "burndown: no work left (green-gate-sufficient backlog is empty). Halting."
    break
  fi
  echo "cycle $cycle: $GAP"
done
