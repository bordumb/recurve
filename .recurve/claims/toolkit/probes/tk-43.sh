#!/usr/bin/env bash
# TK-43: records may carry branches — the road not taken (F3.1). The
# run-record schema gains an optional `branches` field: an array of objects,
# each with `kind` (attempt|decomposition|approach), `description`, and
# `rejected_because`. The field is additive and schema-validated: `recurve
# record append` accepts a record carrying well-formed branch entries and
# stores them verbatim, but rejects one whose branch entry is missing
# `rejected_because`.
#
# RED-first proof, against the REAL engine on a throwaway project:
#   · a record with two well-formed branches -> append accepts it, stored verbatim
#   · the same record with a branch missing rejected_because -> append rejects it
#
# With $TRAP_FIXTURE: `claims` asserts a malformed branch entry (missing
# rejected_because) is accepted. The correct engine contradicts it (RED).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
RECURVE="$ROOT/recurve"
. "$DIR/_toy.sh"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

build_project() {  # $1=dir — a minimal project record append can target
  mkdir -p "$1/claims/x"
  cat > "$1/recurve.toml" <<'TOML'
[project]
name = "fixture"
label = "suite"
default_reads = "none"
schema = "1"

[target]
tree = "."

[reads.none]
method = "none"

[suites.x]
dir = "claims/x"
rebuild = ""
harness = []
TOML
  cat > "$1/r_ok.json" <<'JSON'
{"schema_version":"1.0.0","project":"fixture","cycle":"tk43-ok","status":"closed","attempts":1,"wall_clock_s":2,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0},"branches":[{"kind":"attempt","description":"tried the naive approach first","rejected_because":"too slow on the real dataset"},{"kind":"approach","description":"considered a cache layer","rejected_because":"lacks the infra this cycle"}]}
JSON
  cat > "$1/r_bad.json" <<'JSON'
{"schema_version":"1.0.0","project":"fixture","cycle":"tk43-bad","status":"closed","attempts":1,"wall_clock_s":2,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0},"branches":[{"kind":"attempt","description":"tried the naive approach first"}]}
JSON
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  build_project "$W/p"
  ( cd "$W/p" && python3 "$RECURVE" record append --file r_bad.json >/dev/null 2>&1 )
  rc=$?
  case "$rc" in
    1) exit 1 ;;   # malformed branch entry rejected (real, correct behavior)
    0) echo "malformed branch entry accepted (fixture claimed it is)"; exit 0 ;;
    *) echo "record append errored unexpectedly (rc=$rc) — cannot measure"; exit 2 ;;
  esac
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
build_project "$T/a"

( cd "$T/a" && python3 "$RECURVE" record append --file r_ok.json >/dev/null 2>&1 )
rc=$?
[ $rc -eq 0 ] || { echo "ours=record append rc=$rc on well-formed branches oracle=exit 0, accepted"; exit 1; }
python3 - "$T/a/.recurve/state/records.jsonl" <<'PY' || { echo "ours=branches not stored verbatim oracle=two branch entries, kinds and reasons intact"; exit 1; }
import json, sys
line = [l for l in open(sys.argv[1]) if "tk43-ok" in l][0]
rec = json.loads(line)
b = rec.get("branches") or []
assert len(b) == 2, b
assert b[0]["kind"] == "attempt" and b[0]["rejected_because"] == "too slow on the real dataset", b
assert b[1]["kind"] == "approach" and b[1]["rejected_because"] == "lacks the infra this cycle", b
PY

( cd "$T/a" && python3 "$RECURVE" record append --file r_bad.json >/dev/null 2>&1 )
rc=$?
[ $rc -ne 0 ] || { echo "ours=record append exit 0 on a branch missing rejected_because oracle=nonzero exit, rejected"; exit 1; }
grep -q "tk43-bad" "$T/a/.recurve/state/records.jsonl" 2>/dev/null \
  && { echo "ours=malformed record landed in the journal oracle=rejected records never append"; exit 1; }

echo "record append accepts well-formed branches (stored verbatim) and rejects one missing rejected_because"
exit 0
