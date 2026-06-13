#!/usr/bin/env bash
# TK-10: `next --json` exposes the draft backlog (per-suite pending counts)
# and pending adjudication forks — an orchestrator can tell "the spec is
# burned down" from "the next wave is unarmed".
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  OUT="$(cat "$TRAP_FIXTURE/next.json")"
else
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
  cat > "$FIX/claims/x/gaps.draft.yaml" <<'YAML'
- id: X-1
  title: first pending draft
  needs_authoring: true
- id: X-2
  title: second pending draft
  needs_authoring: true
YAML
  printf '## FORK-1: a fork\n- DECIDED: (pending)\n' > "$FIX/ADJUDICATE.md"
  OUT="$(cd "$FIX" && python3 "$ROOT/recurve" next --json 2>/dev/null)" \
    || { echo "engine could not run next --json"; exit 2; }
fi

python3 - "$OUT" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("ours=unparseable next --json oracle=structured triage output"); sys.exit(1)
drafts = d.get("drafts")
if not isinstance(drafts, list) or {"suite": "x", "pending": 2} not in [
        {"suite": x.get("suite"), "pending": x.get("pending")} for x in (drafts or [])]:
    print(f"ours=drafts={drafts!r} oracle=[{{suite: x, pending: 2}}] — the unarmed backlog is invisible"); sys.exit(1)
if d.get("adjudications_pending") != 1:
    print(f"ours=adjudications_pending={d.get('adjudications_pending')!r} oracle=1 pending fork visible"); sys.exit(1)
print("drafts and pending adjudications visible to orchestrators"); sys.exit(0)
PY
