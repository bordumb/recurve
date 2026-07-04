#!/usr/bin/env bash
# EV-8: the price of trust is measured, and the token cap is enforced PER CELL.
# Telemetry parses usage, costs it from the dated table (an unpriced model
# RAISES — never a silent $0), and captures wall-clock. `run_gated_burndown`
# accumulates spend across a cell's many cycles against ONE budget and stops
# starting new cycles once the cap is reached — reporting the stop_reason
# (gate_green vs budget_exhausted) that EV-6 records and EV-7 classifies from.
# The cap is per-cell, not per-cycle: the recorded total is bounded by cap + one
# cycle's overshoot, never many multiples of it. Hermetic: mock cycles, no spend.
#
# RED until telemetry/budget exist. Two traps: cost_usd silently pricing an
# unknown model; a per-cycle cap that lets a cell overshoot without bound.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo silent_zero)"
  out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
sc='$scenario'
if sc=='silent_zero':
    from evallib.adapters.telemetry import cost_usd
    try:
        cost_usd('a-model-with-no-price', 1000, 1000); print('SILENT')
    except KeyError: print('RAISED')
elif sc=='overshoot':
    from evallib.budget import run_gated_burndown
    r=run_gated_burndown(60000, lambda:25000, lambda:False)   # never green, 25k/cycle
    print('BOUNDED' if r['tokens_spent'] <= 60000+25000 else 'OVERSHOT')
" 2>&1)" || { echo "telemetry/budget incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    silent_zero:RAISED) echo "cost_usd refuses to silently price an unknown model"; exit 1 ;;
    overshoot:BOUNDED)  echo "run_gated_burndown caps per cell, bounded overshoot"; exit 1 ;;
    *) echo "guard failed the '$scenario' case: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.adapters.telemetry import parse_usage, cost_usd, wall_clock
    from evallib.budget import TokenBudget, run_capped, run_gated_burndown
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

assert parse_usage({'usage':{'input_tokens':100,'output_tokens':50}}) == (100, 50)
assert abs(cost_usd('claude-haiku-4-5', 1_000_000, 1_000_000) - 6.0) < 1e-9
b = TokenBudget(60000)
for _ in range(3): b.add(20000)
assert b.spent == 60000 and b.remaining() == 0 and b.exhausted()
assert run_capped(60000, 10000) == (6, 60000)
with wall_clock() as t: pass
assert t.elapsed >= 0.0

# run_gated_burndown — the wired per-cell cap-stop feeding the terminal state:
# gate goes green after 2 cycles -> stop gate_green
gc = iter([False, False, True]); calls=[0]
def cyc(): calls[0]+=1; return 10000
r = run_gated_burndown(60000, cyc, lambda: next(gc))
assert r['stop_reason']=='gate_green' and r['cycles']==2, r
# never green, 10k/cycle, cap 60k -> budget_exhausted at the cap
r = run_gated_burndown(60000, lambda: 10000, lambda: False)
assert r['stop_reason']=='budget_exhausted' and r['tokens_spent']==60000, r
# an over-cap cycle (25k) still stops within one cycle of the cap — PER CELL, not per cycle
r = run_gated_burndown(60000, lambda: 25000, lambda: False)
assert r['stop_reason']=='budget_exhausted' and r['tokens_spent'] <= 60000+25000 and r['cycles']==3, r
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=telemetry/budget wrong: $(printf '%s' "$out"|tail -1) oracle=usage+cost+wall-clock, per-cell cap with bounded overshoot"; exit 1; }
echo "telemetry captures the price of trust; run_gated_burndown enforces a per-cell cap (bounded overshoot, stop_reason recorded)"
exit 0
