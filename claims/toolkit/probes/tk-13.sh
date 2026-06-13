#!/usr/bin/env bash
# TK-13: `report` renders the deterministic run dataset — progress from the
# ledger, cycle durations + ETA from the records, and the honesty scan over
# the records' git range — with no narrator configured and no network.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable — cannot measure"; exit 2; }

FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT
GIT=(git -c user.name=probe -c user.email=probe@invalid -c commit.gpgsign=false)

# A tiny target: a git tree whose second commit ADDS a TODO line the honesty
# scan must count, a ledger with closed/open/review-gated gaps, and three
# synthetic (schema-shaped) cycle records.
mkdir -p "$FIX/tree/src"
printf 'def run():\n    return 1\n' > "$FIX/tree/src/main.py"
"${GIT[@]}" -C "$FIX/tree" init -q
"${GIT[@]}" -C "$FIX/tree" add -A
"${GIT[@]}" -C "$FIX/tree" commit -qm base
printf '    # TODO: tighten this check\n' >> "$FIX/tree/src/main.py"
"${GIT[@]}" -C "$FIX/tree" add -A
"${GIT[@]}" -C "$FIX/tree" commit -qm sculpt

cat > "$FIX/recurve.toml" <<'TOML'
[project]
name = "fixture"
label = "suite"
default_reads = "none"
schema = "1"

[target]
tree = "tree"

[reads.none]
method = "none"

[suites.x]
dir = "claims/x"
rebuild = ""
harness = []
TOML
mkdir -p "$FIX/claims/x" "$FIX/.recurve/state"
cat > "$FIX/claims/x/gaps.yaml" <<'YAML'
- id: X-1
  title: first behavior
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  smallest_fix: f
  probe: probes/p.sh
- id: X-2
  title: second behavior
  class: wire-mismatch
  status: closed
  severity: feature
  reads: none
  smallest_fix: f
  probe: probes/p.sh
- id: X-3
  title: third behavior
  class: missing-surface
  status: open
  severity: feature
  reads: none
  smallest_fix: f
  probe: probes/p.sh
- id: X-4
  title: a fail-closed loosening
  class: security-tradeoff
  status: open
  severity: feature
  reads: none
  smallest_fix: f
  probe: probes/p.sh
YAML
cat > "$FIX/.recurve/state/records.jsonl" <<'JSON'
{"schema_version":"1.0.0","project":"fixture","run_id":"fix-run","cycle":"c1","gap":"X-1","suite":"x","class":"missing-surface","severity":"feature","status":"closed","attempts":1,"wall_clock_s":300,"net_new_gaps":0,"started_at":"2000-01-01T00:00:00Z","verdicts_before":{"green":0,"red":3},"verdicts_after":{"green":1,"red":2}}
{"schema_version":"1.0.0","project":"fixture","run_id":"fix-run","cycle":"c2","gap":"X-2","suite":"x","class":"wire-mismatch","severity":"feature","status":"closed","attempts":2,"wall_clock_s":600,"net_new_gaps":1,"started_at":"2000-01-01T01:00:00Z","verdicts_before":{"green":1,"red":2},"verdicts_after":{"green":2,"red":1}}
{"schema_version":"1.0.0","project":"fixture","run_id":"fix-run","cycle":"c3","gap":"X-3","suite":"x","class":"missing-surface","severity":"feature","status":"parked","attempts":3,"wall_clock_s":120,"net_new_gaps":0,"started_at":"2000-01-01T02:00:00Z","parked_reason":"stuck on harness","verdicts_before":{"green":2,"red":1},"verdicts_after":{"green":2,"red":1}}
JSON

if [ -n "${TRAP_FIXTURE:-}" ]; then
  ENGINE="$TRAP_FIXTURE/engine"
else
  ENGINE="python3 $ROOT/recurve"
fi

OUT="$(cd "$FIX" && $ENGINE report 2>/dev/null)" \
  || { echo "ours=report exited nonzero oracle=deterministic report, exit 0"; exit 1; }

for sec in '## Progress' '## Cycles' '## ETA' 'Honesty markers'; do
  printf '%s' "$OUT" | grep -q "$sec" \
    || { echo "ours=report lacks '$sec' oracle=progress+durations+ETA+honesty in one deterministic pass"; exit 1; }
done
printf '%s' "$OUT" | grep 'TODO' | grep -Eq '\| *[1-9][0-9]* *\|$' \
  || { echo "ours=seeded TODO addition not counted oracle=honesty scan counts added suppression lines"; exit 1; }
printf '%s' "$OUT" | grep -q 'insufficient data' \
  && { echo "ours=ETA reads insufficient with 2 closed cycles recorded oracle=projection from the last closed cycles"; exit 1; }
printf '%s' "$OUT" | grep -q '## Narrative' \
  && { echo "ours=narrative present unprompted oracle=no narrator, no network — deterministic only"; exit 1; }
echo "deterministic run dataset rendered from records+ledger+git; the seeded TODO was counted"
exit 0
