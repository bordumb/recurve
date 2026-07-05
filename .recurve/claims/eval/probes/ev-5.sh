#!/usr/bin/env bash
# EV-5: Analysis is a deterministic, order-invariant pure function —
# results.jsonl in, the §4 tables out (per-cell shipped-bad-work rate, FDR,
# ΔFDR per model, oracle pass rate, paired McNemar, Wilson intervals). Same
# input in any order → byte-identical output; no notebook state, no manual step.
#
# RED until analyze exists. The trap feeds the same results in a shuffled order
# and proves the output is byte-identical (a future order-sensitive analyze
# would break it).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIXTURE='
import json, random
rows = []
def add(model, arm, tid, declared, verdict):
    rows.append({"model":model,"arm":arm,"task_id":tid,"cell_id":f"{model}-{arm}-{tid}",
                 "budget":60000,"seed":0,"declared_done":declared,"oracle_verdict":verdict})
# model mA: A0 ships 2 bad of 3 declared (FDR 2/3); A3 refuses task2, passes t1/t3 (FDR 0)
add("mA","A0","t1",True,"pass"); add("mA","A0","t2",True,"fail"); add("mA","A0","t3",True,"fail")
add("mA","A3","t1",True,"pass"); add("mA","A3","t2",False,"fail"); add("mA","A3","t3",True,"pass")
# model mB: A0 ships 1 bad of 2 declared; A3 clean
add("mB","A0","t1",True,"pass"); add("mB","A0","t2",True,"fail")
add("mB","A3","t1",True,"pass"); add("mB","A3","t2",True,"pass")
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(EVALPATH="$EVAL" python3 -c "
import sys, random; sys.path.insert(0,'$EVAL')
$FIXTURE
from evallib.analyze import analyze_rows
a = analyze_rows(list(rows))
r = list(rows); random.Random(1).shuffle(r)
b = analyze_rows(r)
print('STABLE' if a == b else 'ORDER_SENSITIVE')
" 2>&1)" || { echo "analyze incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^STABLE$'; then
    echo "analyze is order-invariant"; exit 1        # guard holds → RED
  fi
  echo "analyze output depends on input order (fixture claimed it does)"; exit 0   # broken → trap fails
fi

out="$(EVALPATH="$EVAL" python3 -c "
import sys, random; sys.path.insert(0,'$EVAL')
$FIXTURE
try:
    from evallib.analyze import analyze_rows, metrics
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
m = metrics(list(rows))
# FDR(mA,A0)=2/3, FDR(mA,A3)=0 -> dFDR(mA)=2/3 ; shipped_bad(mA,A0)=2/3
assert abs(m['mA']['A0']['fdr'] - 2/3) < 1e-9, m['mA']['A0']
assert m['mA']['A3']['fdr'] == 0.0, m['mA']['A3']
assert abs(m['mA']['delta_fdr'] - 2/3) < 1e-9, m['mA']
assert abs(m['mA']['A0']['shipped_bad_rate'] - 2/3) < 1e-9, m['mA']['A0']
# byte-stable + order-invariant
a = analyze_rows(list(rows)); b = analyze_rows(list(rows))
assert a == b, 'not deterministic across runs'
r = list(rows); random.Random(2).shuffle(r)
assert analyze_rows(r) == a, 'not order-invariant'
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "analyze is deterministic + order-invariant; FDR/ΔFDR/shipped-bad computed correctly"
  exit 0
fi
echo "ours=analyze wrong: $(printf '%s' "$out" | tail -1) oracle=deterministic tables, correct FDR/ΔFDR"
exit 1
