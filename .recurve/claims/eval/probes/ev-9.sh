#!/usr/bin/env bash
# EV-9: the figures are data, gated like the tables. `figure_specs` is a pure,
# deterministic, order-invariant function of the results: the hero dumbbell
# (A0->A3 shipped-bad per model with Wilson-95% endpoints, delta, refused
# counts) and the Figure-2 decomposition (among A0-shipped-bad tasks, what A3
# did: fixed / refused / also-shipped-bad). Two honesty craft rules are encoded
# as guards: `spec_is_honest` requires the hero x-domain to be the full [0,1]
# (never a truncated axis) and a synthetic watermark whenever the data is fake.
# The matplotlib renderer emits byte-stable SVG (fixed rcParams, no timestamps)
# into the same deterministic pass — oracle-waived where matplotlib is absent.
#
# RED until figure_specs exists. The trap is a truncated-axis hero spec, which
# spec_is_honest must reject.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIX='
rows=[]
def add(m,a,t,d,v,o=None):
    r={"model":m,"arm":a,"task_id":t,"cell_id":f"{m}-{a}-{t}","budget":60000,"seed":0,
       "declared_done":d,"oracle_verdict":v}
    if o: r["gate_outcome"]=o
    rows.append(r)
# mA: A0 ships bad on t2,t3; A3 fixes t2, refuses t3, passes t1/t4
add("mA","A0","t1",True,"pass"); add("mA","A0","t2",True,"fail")
add("mA","A0","t3",True,"fail"); add("mA","A0","t4",True,"pass")
add("mA","A3","t1",True,"pass"); add("mA","A3","t2",True,"pass")
add("mA","A3","t3",False,"fail","gate_refused"); add("mA","A3","t4",True,"pass")
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.analyze import figure_specs, spec_is_honest
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
$FIX
spec=figure_specs(rows)
spec['hero']['x_domain']=[0.4,0.6]     # truncated axis — the honesty violation
print('ACCEPTED' if spec_is_honest(spec) else 'REJECTED')
" 2>&1)" || { echo "figure_specs incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^REJECTED$'; then
    echo "spec_is_honest rejects a truncated-axis hero"; exit 1   # guard holds → RED
  fi
  echo "spec_is_honest accepted a truncated axis (fixture claimed it does)"; exit 0
fi

out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.analyze import figure_specs, spec_is_honest, wilson
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
$FIX
spec=figure_specs(rows)
h=spec['hero']
assert h['kind']=='dumbbell' and h['x_domain']==[0.0,1.0], h
row=[r for r in h['rows'] if r['model']=='mA'][0]
assert abs(row['baseline']['rate']-0.5)<1e-9 and row['gated']['rate']==0.0, row   # shipped-bad A0 2/4, A3 0/4
assert abs(row['delta']-0.5)<1e-9, row
lo,hi=wilson(2,4); assert abs(row['baseline']['ci_lo']-lo)<1e-9 and abs(row['baseline']['ci_hi']-hi)<1e-9, row
assert row['gated']['refused']==1, row
d=[r for r in spec['decomposition']['rows'] if r['model']=='mA'][0]
assert d['among_baseline_bad']==2 and d['fixed']==1 and d['refused']==1 and d['also_bad']==0, d
# deterministic + order-invariant
import random
a=figure_specs(rows); r2=list(rows); random.Random(3).shuffle(r2)
assert figure_specs(r2)==a, 'not order-invariant'
assert spec_is_honest(a)
# synthetic watermark propagates
s=figure_specs(rows, synthetic=True); assert s['synthetic'] is True and spec_is_honest(s)
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=figure_specs wrong: $(printf '%s' "$out"|tail -1) oracle=deterministic hero+decomposition, honest axis"; exit 1; }

# render is byte-stable where matplotlib is present (oracle-waived otherwise)
python3 -c "import matplotlib" 2>/dev/null && {
  python3 -c "
import sys,tempfile,pathlib; sys.path.insert(0,'$EVAL')
from evallib.analyze import figure_specs
$FIX
try:
    from evallib.render import render_figures
except Exception as e:
    print('render missing:', e); raise SystemExit(1)
d1=pathlib.Path(tempfile.mkdtemp()); d2=pathlib.Path(tempfile.mkdtemp())
spec=figure_specs(rows)
render_figures(spec, d1); render_figures(spec, d2)
a=(d1/'hero.svg').read_bytes(); b=(d2/'hero.svg').read_bytes()
assert a==b, 'hero.svg not byte-stable across renders'
assert (d1/'hero.pdf').exists() and (d1/'decomposition.svg').exists()
print('render OK')
" || { echo "ours=render not byte-stable/complete oracle=deterministic SVG+PDF, no timestamps"; exit 1; }
  echo "figure_specs is deterministic + honest; matplotlib render is byte-stable"
} || echo "figure_specs is deterministic + honest (render oracle-waived: matplotlib absent)"
exit 0
