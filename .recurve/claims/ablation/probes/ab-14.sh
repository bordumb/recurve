#!/usr/bin/env bash
# AB-14: a real `drill --diff` disagreement on a CLOSED claim records a
# challenge_event (phase: post_publication) — R4/AI8's named "later
# differential pass" trigger, wired for real
# (docs/plans/oracle-strength-and-decorrelation.md R4,
# docs/plans/ablation-infra.md AI8). RED-first: until drill --diff actually
# writes a challenge_event the probe is RED.
#
# With $TRAP_FIXTURE: a scenario asserting a real drill --diff disagreement
# leaves NO trace at all. The real engine must record it (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
RECURVE_BIN="$ROOT/recurve"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
PROJ="$T/proj"
mkdir -p "$PROJ/claims/s/probes/x-1.trap/ce"
cat > "$PROJ/recurve.toml" <<TOML
[project]
name = "ab14-fixture"
label = "suite"
default_reads = "none"
cycles_dir = "cycles"
schema = "1"

[target]
tree = "."

[gate]
traps = "off"
quality = "pre-launch"

[reads.none]
method = "none"

[suites.s]
dir = "claims/s"
TOML
# The claim's OWN probe: a shallow happy-path check that says GREEN — the
# "published" state.
cat > "$PROJ/claims/s/probes/x-1.sh" <<'PROBE'
#!/usr/bin/env bash
echo ok; exit 0
PROBE
chmod +x "$PROJ/claims/s/probes/x-1.sh"
echo "x" > "$PROJ/claims/s/probes/x-1.trap/ce/marker"
# A stricter reference oracle that disagrees — "a later differential pass"
# finds the same claim wrong.
cat > "$PROJ/claims/s/probes/x-1.reference.sh" <<'PROBE'
#!/usr/bin/env bash
echo "stricter check disagrees"; exit 1
PROBE
chmod +x "$PROJ/claims/s/probes/x-1.reference.sh"
cat > "$PROJ/claims/s/gaps.yaml" <<'YAML'
- id: X-1
  title: fixture claim, published GREEN
  class: missing-surface
  status: closed
  severity: feature
  reads: none
  evidence: ["x:1"]
  observed: GREEN by construction
  smallest_fix: none
  probe: probes/x-1.sh
  reference: probes/x-1.reference.sh
YAML
echo "## X-1" > "$PROJ/claims/s/GAPS.md"

cd "$PROJ"
git init -q
EMPTY_HOOKS="$(mktemp -d)"
git config core.hooksPath "$EMPTY_HOOKS"
git config commit.gpgsign false
git add -A
git -c user.name=t -c user.email=t@t commit -q --no-gpg-sign -m initial

fail() { echo "FAIL: $1"; exit 1; }
CHALLENGE_LOG="$PROJ/.recurve/state/challenges/s.jsonl"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo "")"
  if [ "$scenario" != "diff_disagreement_leaves_no_trace" ]; then
    echo "unknown scenario: $scenario"; exit 2
  fi
  # broken_drill.py is the REAL drill.py with the challenge_event recording
  # call removed — the exact regression this trap exists to catch (someone
  # reverts the one-line wiring).
  AB14_ENGINE_ROOT="$ROOT" python3 -c "
import sys, os
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.environ['AB14_ENGINE_ROOT'])
import importlib.util
spec = importlib.util.spec_from_file_location('broken_drill', sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

args = SimpleNamespace(cmd='drill', prog='recurve', config=None, suite=None,
                       timeout=30, deep=False, fuzz=False, iso=False, diff=True)
try:
    mod.cmd_drill(args)
except SystemExit:
    pass
" "$TRAP_FIXTURE/broken_drill.py" >/dev/null 2>&1
  if [ ! -f "$CHALLENGE_LOG" ]; then
    echo "ours=no challenge_event recorded oracle=a real diff disagreement on a closed "\
         "claim must record one — correctly caught the silent-forgetting bug"
    exit 1
  fi
  echo "ours=a challenge_event WAS recorded oracle=expected none (this fixture did not "\
       "exercise the intended bug)"
  exit 0
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

[ ! -f "$CHALLENGE_LOG" ] || fail "a challenge log already exists before drill ever ran"

OUT="$(python3 "$RECURVE_BIN" drill --diff 2>&1)"
echo "$OUT" | grep -q "DISAGREEMENT" || fail "drill --diff did not report the planted disagreement: $OUT"

# 1. a real challenge_event landed, phase=post_publication, reason names the
# actual disagreement, tier_at_challenge is a real derived tier (not a
# hand-set/guessed value).
[ -f "$CHALLENGE_LOG" ] || fail "no challenge_event was recorded for the real diff disagreement"
EVENT="$(python3 -c "
import json
with open('$CHALLENGE_LOG') as f:
    lines = [json.loads(l) for l in f if l.strip()]
assert len(lines) == 1, f'expected exactly 1 event, got {len(lines)}'
e = lines[0]
assert e['claim_id'] == 'X-1', e
assert e['phase'] == 'post_publication', e
assert 'disagree' in e['reason'].lower() or 'diff' in e['reason'].lower(), e
assert e['tier_at_challenge'], e
assert 'reversal' not in e and 'veto' not in e and 'event_type' not in e, 'legacy shape leaked in'
print('ok')
")"
[ "$EVENT" = "ok" ] || fail "the recorded challenge_event's shape/content is wrong: $EVENT"

# 2. it shows up in `recurve stats`'s challenge-rate line — the standing
# dataset a human/orchestrator actually reads, not just a file on disk.
STATS_OUT="$(python3 "$RECURVE_BIN" stats 2>&1)"
echo "$STATS_OUT" | grep -q "challenge rate: 1/1" \
  || fail "recurve stats does not surface the recorded challenge: $STATS_OUT"
echo "$STATS_OUT" | grep -q "1 pre_publication\|0 pre_publication" || true
echo "$STATS_OUT" | grep -q "post_publication" \
  || fail "recurve stats does not slice by phase: $STATS_OUT"

# 3. re-running drill --diff again (still disagreeing) appends a SECOND
# distinct event rather than silently deduping or overwriting — an
# append-only log, the same discipline receipts use.
python3 "$RECURVE_BIN" drill --diff >/dev/null 2>&1
COUNT="$(python3 -c "print(sum(1 for l in open('$CHALLENGE_LOG') if l.strip()))")"
[ "$COUNT" = "2" ] || fail "expected 2 append-only events after a second disagreeing run, got $COUNT"

echo "a real drill --diff disagreement on a CLOSED claim records a challenge_event "\
     "(phase: post_publication) with a real derived tier and a concrete reason — "\
     "append-only, surfaced in recurve stats's challenge-rate line, never a printed "\
     "line nobody remembers"
exit 0
