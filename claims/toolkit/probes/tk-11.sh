#!/usr/bin/env bash
# TK-11: `record append` is idempotent — the agent (per RUN.md) and the loop
# (per burndown) may both append one cycle's record; the dataset keeps ONE
# observation, never a double-counted cycle.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT
cat > "$FIX/recurve.toml" <<'TOML'
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
mkdir -p "$FIX/claims/x"
cat > "$FIX/r.json" <<'JSON'
{"schema_version":"1.0.0","project":"fixture","cycle":"tk11-probe","status":"closed","attempts":1,"wall_clock_s":2,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0}}
JSON

if [ -n "${TRAP_FIXTURE:-}" ]; then
  ENGINE="$TRAP_FIXTURE/engine"
else
  ENGINE="python3 $ROOT/recurve"
fi

( cd "$FIX" \
  && $ENGINE record append --file r.json >/dev/null 2>&1 \
  && $ENGINE record append --file r.json >/dev/null 2>&1 ) \
  || { echo "engine could not append a valid record"; exit 2; }

N="$(grep -c tk11-probe "$FIX/.recurve/state/records.jsonl" 2>/dev/null || echo 0)"
if [ "$N" -eq 1 ]; then
  echo "one record appended twice lands once"; exit 0
fi
echo "ours=$N journal line(s) oracle=1 — a re-appended record must not double-count"; exit 1
