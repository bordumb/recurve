#!/usr/bin/env bash
# EV-3: the Runner turns a manifest into a pinned matrix and drives it as a
# resumable work queue. `plan.expand` writes the cross product (task × arm ×
# model × budget × seed) with cell IDs derived from coordinates, BEFORE any
# agent runs. `runner.run` seals exactly one row per cell and — the resume
# invariant — a re-run over a completed matrix produces ZERO new agent
# invocations. Tested with a mock adapter (no live agent, no spend).
#
# RED until plan/runner exist. The trap is a runner that re-invokes the agent
# on already-sealed cells; the probe proves resume produces zero new calls.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

RUN_BODY='
import sys, tempfile, pathlib, json
sys.path.insert(0, EVALPATH)
from evallib.plan import expand
from evallib.runner import run

manifest = {"matrix": {"models": ["m1","m2"], "arms": ["A0","A3"],
                       "budgets": [60000], "seeds": [0]}}
tasks = [{"task_id":"t/1","instruct_prompt":"a","test":"x"},
         {"task_id":"t/2","instruct_prompt":"b","test":"y"}]
cells = expand(manifest, tasks)
assert len(cells) == 8, f"cross product wrong: {len(cells)}"          # 2*2*2*1*1
ids = [c["cell_id"] for c in cells]
assert len(set(ids)) == 8, "cell ids not unique"
assert cells == expand(manifest, tasks), "expand not deterministic"

calls = {"n": 0}
def adapter(cell, workspace):
    calls["n"] += 1
    return {"declared_done": True, "tokens": 10}

d = pathlib.Path(tempfile.mkdtemp())
res = d / "results.jsonl"
run(cells, res, adapter, workspace_root=d / "cells")
first = calls["n"]
sealed = [json.loads(l) for l in res.read_text().splitlines() if l.strip()]
assert first == 8 and len(sealed) == 8, f"first run: {first} calls, {len(sealed)} rows"
# RESUME: a second run over the completed matrix invokes the agent zero times
run(cells, res, adapter, workspace_root=d / "cells")
resumed = calls["n"] - first
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$RUN_BODY
print('RESUMED_CALLS', resumed)
" 2>&1)" || { echo "runner incomplete: $out"; exit 2; }
  n="$(printf '%s\n' "$out" | awk '/RESUMED_CALLS/{print $2}')"
  if [ "$n" = "0" ]; then echo "runner resumes with zero new invocations"; exit 1; fi   # invariant holds → RED
  echo "runner re-invoked on sealed cells ($n) (fixture claimed it does)"; exit 0        # broken → trap fails
fi

out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$RUN_BODY
assert resumed == 0, f'resume re-invoked {resumed} times'
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "runner expands a pinned matrix, seals one row per cell, and resumes with zero new invocations"
  exit 0
fi
echo "ours=runner/plan wrong: $(printf '%s' "$out" | tail -1) oracle=deterministic matrix + resume with zero new invocations"
exit 1
