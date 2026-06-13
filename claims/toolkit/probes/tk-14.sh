#!/usr/bin/env bash
# TK-14: `report --narrate` pipes the deterministic report + the cycle
# records to the configured narrator and appends its prose; with no narrator
# configured the flag fails clean (exit 2); a dying narrator costs only the
# prose — the deterministic report still renders, exit 1.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT

base_fixture() { # base_fixture <dir>
  mkdir -p "$1/claims/x" "$1/.recurve/state"
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
  cat > "$1/claims/x/gaps.yaml" <<'YAML'
- id: X-1
  title: behavior
  class: missing-surface
  status: open
  severity: feature
  reads: none
  smallest_fix: f
  probe: probes/p.sh
YAML
  cat > "$1/.recurve/state/records.jsonl" <<'JSON'
{"schema_version":"1.0.0","project":"fixture","cycle":"c1","gap":"X-1","suite":"x","status":"closed","attempts":1,"wall_clock_s":60,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0}}
{"schema_version":"1.0.0","project":"fixture","cycle":"c2","gap":"X-1","suite":"x","status":"closed","attempts":1,"wall_clock_s":90,"verdicts_before":{"green":0,"red":1},"verdicts_after":{"green":1,"red":0}}
JSON
}

A="$FIX/a"; base_fixture "$A"
cat >> "$A/recurve.toml" <<'TOML'

[report]
narrator = "sh -c 'cat >/dev/null; echo NARRATIVE-OK'"
TOML

B="$FIX/b"; base_fixture "$B"

C="$FIX/c"; base_fixture "$C"
cat >> "$C/recurve.toml" <<'TOML'

[report]
narrator = "sh -c 'cat >/dev/null; exit 7'"
narrator_timeout = 10
TOML

if [ -n "${TRAP_FIXTURE:-}" ]; then
  ENGINE="$TRAP_FIXTURE/engine"
else
  ENGINE="python3 $ROOT/recurve"
fi

OUT="$(cd "$A" && $ENGINE report --narrate 2>/dev/null)"; RC=$?
[ "$RC" -eq 0 ] || { echo "ours=--narrate exited $RC oracle=0 with prose appended"; exit 1; }
printf '%s' "$OUT" | grep -q '## Narrative' \
  || { echo "ours=no Narrative section oracle=narrator prose appended under '## Narrative'"; exit 1; }
printf '%s' "$OUT" | grep -q 'NARRATIVE-OK' \
  || { echo "ours=narrator stdout missing oracle=its prose lands in the report"; exit 1; }

(cd "$B" && $ENGINE report --narrate >/dev/null 2>&1); RC=$?
[ "$RC" -eq 2 ] || { echo "ours=--narrate without config exited $RC oracle=clean usage error, exit 2"; exit 1; }
OUT="$(cd "$B" && $ENGINE report 2>/dev/null)" \
  || { echo "ours=plain report failed without narrator oracle=the deterministic report needs none"; exit 1; }
printf '%s' "$OUT" | grep -q '## Progress' \
  || { echo "ours=plain report lacks Progress oracle=deterministic report renders without the flag"; exit 1; }

OUT="$(cd "$C" && $ENGINE report --narrate 2>/dev/null)"; RC=$?
[ "$RC" -eq 1 ] || { echo "ours=dying narrator exited $RC oracle=1 (prose lost, report kept)"; exit 1; }
printf '%s' "$OUT" | grep -q '## Progress' \
  || { echo "ours=deterministic report lost to a dying narrator oracle=it must always render"; exit 1; }

echo "narrator prose appended; missing config fails clean; a dying narrator never costs the report"
exit 0
