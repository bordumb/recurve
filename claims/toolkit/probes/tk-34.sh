#!/usr/bin/env bash
# TK-34: exports are evidence, so they must be reproducible and side-effect
# free: two runs of `recurve trajectories` over the same state are
# byte-identical (stable row order, sorted keys), and the command mutates
# neither the records nor the ledger (read-only by construction).
#
# With $TRAP_FIXTURE: `claims` asserts the export rewrites records.jsonl.
# The correct engine leaves it untouched (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

build_project() {  # $1=dir — several records across two gaps, out-of-order input
  toy_init "$1"
  toy_claim "$1" g-1 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_claim "$1" g-2 yes <<'SH'
#!/bin/sh
exit 0
SH
  toy_record "$1" G-2 closed 2 run-b cycle-3
  toy_record "$1" G-1 closed 1 run-a cycle-1
  toy_record "$1" G-1 parked 1 run-b cycle-2
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  before="$(sha "$W/p/.recurve/state/records.jsonl")"
  ( cd "$W/p" && python3 "$RECURVE" trajectories >/dev/null 2>&1 ) || { echo "trajectories errored"; exit 2; }
  after="$(sha "$W/p/.recurve/state/records.jsonl")"
  if [ "$before" = "$after" ]; then
    echo "records.jsonl untouched by export (fixture claimed it is rewritten)"; exit 1
  fi
  exit 0   # the exporter mutated the evidence it exports
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

rec_before="$(sha "$T/a/.recurve/state/records.jsonl")"
led_before="$(sha "$T/a/claims/s/gaps.yaml")"
( cd "$T/a" && python3 "$RECURVE" trajectories --include-unverified >"$T/run1" 2>/dev/null ); rc=$?
[ $rc -eq 0 ] || { echo "ours=trajectories rc=$rc oracle=exit 0"; exit 1; }
( cd "$T/a" && python3 "$RECURVE" trajectories --include-unverified >"$T/run2" 2>/dev/null )

cmp -s "$T/run1" "$T/run2" \
  || { echo "ours=two exports of identical state differ oracle=byte-identical (stable sort, sorted keys)"; exit 1; }
[ -s "$T/run1" ] || { echo "ours=empty export oracle=three records export"; exit 1; }
[ "$rec_before" = "$(sha "$T/a/.recurve/state/records.jsonl")" ] \
  || { echo "ours=export mutated records.jsonl oracle=read-only command"; exit 1; }
[ "$led_before" = "$(sha "$T/a/claims/s/gaps.yaml")" ] \
  || { echo "ours=export mutated the ledger oracle=read-only command"; exit 1; }

echo "trajectories is deterministic (byte-identical re-runs) and read-only (records + ledger untouched)"
exit 0
