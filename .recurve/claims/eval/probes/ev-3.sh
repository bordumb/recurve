#!/usr/bin/env bash
# EV-3: the Runner turns a manifest into a pinned matrix and drives it as a
# resumable, CRASH-RESILIENT work queue. `plan.expand` writes the cross product
# (task × arm × model × budget × seed) with coordinate-derived cell ids before
# any agent runs. `runner.run` seals each cell's row the moment it finishes
# (append + flush + fsync), so:
#   - a crash mid-run leaves every completed cell durable (resume loses only
#     the in-flight cell);
#   - one adapter that raises is sealed as status=error and the run continues;
#   - a re-run skips sealed ids (errors included) — zero new invocations on a
#     completed matrix;
#   - a truncated final line (a crash caught mid-write) is skipped by
#     sealed_ids, never fatal on resume.
# Tested with mock adapters — no live agent, no spend.
#
# RED until the runner is per-cell-durable. The trap crashes mid-run and proves
# the cells that finished before the crash are already sealed.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

BODY='
import sys, tempfile, pathlib, json
sys.path.insert(0, EVALPATH)
from evallib.plan import expand
from evallib.runner import run, sealed_ids

manifest={"matrix":{"models":["m1"],"arms":["A0"],"budgets":[60000],"seeds":[0]}}
tasks=[{"task_id":f"t/{i}","instruct_prompt":"x","test":"y"} for i in range(5)]
cells=expand(manifest, tasks)           # 5 cells, deterministic order
D=pathlib.Path(tempfile.mkdtemp())

class Boom(BaseException): pass         # BaseException → NOT caught as a cell error; a real crash
def crash_on(k):
    n={"i":0}
    def a(cell, ws):
        n["i"]+=1
        if n["i"]==k: raise Boom()
        return {"declared_done":True,"tokens":1}
    return a
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$BODY
res=D/'r.jsonl'
try:
    run(cells, res, crash_on(3), workspace_root=D/'c', workers=1)  # crashes on cell 3
except Boom:
    pass
print('SEALED', len(sealed_ids(res)))     # cells 1,2 must already be durable
" 2>&1)" || { echo "runner incomplete: $out"; exit 2; }
  n="$(printf '%s\n' "$out" | awk '/SEALED/{print $2}')"
  if [ "$n" = "2" ]; then echo "the two cells that finished before the crash are sealed"; exit 1; fi
  echo "a mid-run crash left $n cells sealed (fixture claimed work is lost)"; exit 0
fi

out="$(EVALPATH="$EVAL" python3 -c "
EVALPATH='$EVAL'
$BODY
# --- basic: deterministic matrix + resume with zero new invocations ---
assert len(cells)==5 and len(set(c['cell_id'] for c in cells))==5
assert cells==expand(manifest, tasks)
calls={'n':0}
def ok(cell, ws): calls['n']+=1; return {'declared_done':True,'tokens':1}
res=D/'a.jsonl'
run(cells, res, ok, workspace_root=D/'ca'); first=calls['n']
assert first==5 and len(sealed_ids(res))==5
run(cells, res, ok, workspace_root=D/'ca'); assert calls['n']==first   # resume: 0 new

# --- crash resilience: cells finished before a crash are durable ---
res2=D/'b.jsonl'
try:
    run(cells, res2, crash_on(3), workspace_root=D/'cb', workers=1)
except Boom: pass
assert sealed_ids(res2)=={cells[0]['cell_id'], cells[1]['cell_id']}, sealed_ids(res2)
# resume completes the rest; cell 3 (never sealed) re-runs, cells 1-2 skipped
resumed={'n':0}
def ok2(cell, ws): resumed['n']+=1; return {'declared_done':True,'tokens':1}
run(cells, res2, ok2, workspace_root=D/'cb')
assert resumed['n']==3 and len(sealed_ids(res2))==5, (resumed['n'], sealed_ids(res2))

# --- one bad cell is sealed as error, the run continues ---
res3=D/'c.jsonl'
def err_on2(cell, ws):
    if cell['cell_id']==cells[1]['cell_id']: raise ValueError('boom')
    return {'declared_done':True,'tokens':1}
n=run(cells, res3, err_on2, workspace_root=D/'cc')
rows=[json.loads(l) for l in res3.read_text().splitlines() if l.strip()]
assert n==5 and len(rows)==5
bad=[r for r in rows if r['cell_id']==cells[1]['cell_id']][0]
assert bad.get('status')=='error' and 'ValueError' in bad.get('error',''), bad

# --- a truncated final line does not break resume ---
res4=D/'d.jsonl'
res4.write_text('{\"cell_id\": \"keep-1\"}\n{\"cell_id\": \"keep-2\"}\n{\"cell_id\": \"trunc')
assert sealed_ids(res4)=={'keep-1','keep-2'}, sealed_ids(res4)
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=runner wrong: $(printf '%s' "$out"|tail -1) oracle=per-cell durable seal, error isolation, resume, partial-line tolerance"; exit 1; }
echo "runner: pinned matrix + per-cell durable sealing (crash-resilient, error-isolated, resumable)"
exit 0
