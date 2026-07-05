#!/usr/bin/env bash
# EV-9: the figures are data, gated like the tables. `figure_specs` is a pure,
# deterministic, order-invariant function of the results: the hero dumbbell
# (A0->A3 shipped-bad per model with Wilson-95% endpoints, delta, refused
# counts) and the Figure-2 decomposition (among A0-shipped-bad tasks, what A3
# did: fixed / refused / also-shipped-bad). Honesty craft rules are encoded as
# guards: `spec_is_honest` requires the hero x-domain to be the full [0,1] (never
# a truncated axis), a synthetic watermark whenever the data is fake, AND every
# endpoint's Wilson CI to lie in [0,1] and bracket its own point (a CI that does
# not contain its estimate is a drawing lie — and it crashes the renderer). The
# matplotlib renderer emits byte-stable SVG (fixed rcParams, no timestamps) into
# the same deterministic pass — oracle-waived where matplotlib is absent.
#
# RED until figure_specs exists. Traps: a truncated-axis hero, and a hero whose
# endpoint CI does not bracket its point — both must be rejected as dishonest.
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
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo truncated_axis)"
  out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.analyze import figure_specs, spec_is_honest
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
$FIX
sc='$scenario'
spec=figure_specs(rows)
if sc=='unbracketed_ci':
    e=spec['hero']['rows'][0]['gated']       # push the lower CI bound ABOVE the point
    e['ci_lo']=e['rate']+0.1
else:                                        # truncated_axis (default, legacy fixture)
    spec['hero']['x_domain']=[0.4,0.6]
print('ACCEPTED' if spec_is_honest(spec) else 'REJECTED')
" 2>&1)" || { echo "figure_specs incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    *:REJECTED) echo "spec_is_honest rejects the '$scenario' dishonesty"; exit 1 ;;   # guard holds → RED
    *)          echo "spec_is_honest accepted '$scenario' (fixture claimed it does)"; exit 0 ;;
  esac
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

# a Wilson interval ALWAYS brackets its own point estimate and stays in [0,1],
# even where boundary FP noise (n=6, k=0 is one such case) would push a bound the
# wrong side of the point — an un-bracketed CI is a drawing lie and a render crash
for k,n in [(0,6),(6,6),(0,4),(4,4),(1,3),(3,3),(0,1),(1,1)]:
    clo,chi=wilson(k,n); p=k/n if n else 0.0
    assert 0.0<=clo<=p<=chi<=1.0, ('wilson does not bracket its point',k,n,clo,chi,p)

# spec_is_honest enforces that bracketing on every endpoint (not just the axis)
bad=figure_specs(rows)
g=bad['hero']['rows'][0]['gated']; g['ci_lo']=g['rate']+0.1     # lo above the point
assert not spec_is_honest(bad), 'accepted a non-bracketing endpoint CI'

# deterministic + order-invariant
import random
a=figure_specs(rows); r2=list(rows); random.Random(3).shuffle(r2)
assert figure_specs(r2)==a, 'not order-invariant'
assert spec_is_honest(a)
# synthetic watermark propagates
s=figure_specs(rows, synthetic=True); assert s['synthetic'] is True and spec_is_honest(s)
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=figure_specs wrong: $(printf '%s' "$out"|tail -1) oracle=deterministic hero+decomposition, honest axis, brackets its CIs"; exit 1; }

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
# the renderer must survive a gated group at exactly rate 0 with an n whose
# Wilson lower bound carries boundary FP noise (n=6) — the smoke-run crash
six=[]
def a6(m,ar,t,dn,v,o=None):
    r={'model':m,'arm':ar,'task_id':t,'cell_id':f'{m}{ar}{t}','budget':1,'seed':0,'declared_done':dn,'oracle_verdict':v}
    if o: r['gate_outcome']=o
    six.append(r)
for i in range(6): a6('m6','A0',f't{i}',True,'fail')            # baseline ships bad on all 6
for i in range(6): a6('m6','A3',f't{i}',False,'fail','gate_refused')  # gated refuses all 6 -> rate 0, n=6
render_figures(figure_specs(six), pathlib.Path(tempfile.mkdtemp()))
print('render OK')
" || { echo "ours=render not byte-stable/complete or crashed on a rate-0 n=6 group oracle=deterministic SVG+PDF, no crash"; exit 1; }
  echo "figure_specs is deterministic + honest (brackets its CIs); matplotlib render is byte-stable"
} || echo "figure_specs is deterministic + honest, brackets its CIs (render oracle-waived: matplotlib absent)"
exit 0
