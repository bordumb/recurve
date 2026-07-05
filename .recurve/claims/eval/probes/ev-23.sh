#!/usr/bin/env bash
# EV-23: the budget-matched control is DOLLARS, not tokens. The O6 smoke proved a
# single `claude -p` session spends 143k-1.15M tokens — 2-19x any 60k token "cap"
# — so a token cap cannot bound spend; the honest, matchable unit is dollars.
# `parse_cost` reads the REAL billed cost (`total_cost_usd`, cache-aware) from the
# agent's own report — never a token-times-price estimate for the cap. The budget
# accounting is float-safe (dollars are fractional), so `run_gated_burndown`
# accumulates a cell's real per-cycle cost against a per-cell DOLLAR cap and stops
# between cycles, bounded by cap + one cycle's cost. Hermetic.
#
# RED until parse_cost exists and the accounting is float-safe. Traps: a cost read
# as $0 when the report carries one (silent free run); a dollar cap ignored
# because the accounting truncates fractional spend to zero (unbounded burndown).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

HELP='
import os, sys; sys.path.insert(0, os.environ["EVAL"])
from evallib.adapters.telemetry import parse_cost
from evallib.budget import TokenBudget, run_gated_burndown
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo cost_silently_zero)"
  out="$(EVAL="$EVAL" python3 -c "
$HELP
sc='$scenario'
if sc=='cost_silently_zero':
    c=parse_cost({'total_cost_usd': 0.42, 'usage': {}})
    print('REAL' if abs(c-0.42)<1e-9 else 'ZEROED')
elif sc=='dollar_cap_ignored':
    r=run_gated_burndown(0.30, lambda: 0.12, lambda: False, max_cycles=100)
    print('BOUNDED' if r['cycles']<=5 else 'UNBOUNDED')
" 2>&1)" || { echo "budget incomplete: $out"; exit 2; }
  case "$scenario:$out" in
    cost_silently_zero:REAL)   echo "parse_cost reads the real billed cost, not \$0"; exit 1 ;;
    dollar_cap_ignored:BOUNDED) echo "the dollar burndown stops at the cap (fractional spend counted)"; exit 1 ;;
    *) echo "budget failed the '$scenario' guard: $out (fixture claimed it does)"; exit 0 ;;
  esac
fi

out="$(EVAL="$EVAL" python3 -c "
$HELP
try:
    pass
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# parse_cost reads the agent's real billed cost; missing/None -> 0.0, never guessed
assert abs(parse_cost({'total_cost_usd': 0.42}) - 0.42) < 1e-9
assert parse_cost({}) == 0.0 and parse_cost({'total_cost_usd': None}) == 0.0

# the budget is float-safe (dollars are fractional)
b=TokenBudget(0.25)
b.add(0.10); assert abs(b.spent-0.10)<1e-9 and not b.exhausted(), b.spent
b.add(0.10); assert not b.exhausted(), b.spent
b.add(0.10); assert b.exhausted(), ('float cap not reached', b.spent)   # 0.30 >= 0.25

# a dollar burndown accumulates real per-cycle cost and stops at the per-cell cap,
# bounded by cap + one cycle's cost
r=run_gated_burndown(0.30, lambda: 0.12, lambda: False, max_cycles=1000)
assert r['stop_reason']=='budget_exhausted', r
assert r['cycles']==3, ('wrong cycle count for a 0.12/cycle burndown under 0.30', r)
assert r['tokens_spent'] <= 0.30 + 0.12 + 1e-9, ('overshot cap + one cycle', r['tokens_spent'])

# a gate that greens still stops for the right reason, in dollars
g=run_gated_burndown(1.00, lambda: 0.10, lambda: True)
assert g['stop_reason']=='gate_green' and g['cycles']==0, g
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=dollar budget wrong: $(printf '%s' "$out"|tail -1) oracle=parse_cost real billed cost + float-safe dollar burndown bounded by cap+one cycle"; exit 1; }
echo "budget in dollars: parse_cost reads the real billed cost, the burndown is float-safe and stops at the per-cell dollar cap"
exit 0
