#!/usr/bin/env bash
# EV-8: the price of trust is measured, and the budget is enforced. Telemetry
# parses token usage from the agent's JSON, costs it from the dated price table
# (an unpriced model RAISES — never a silent $0), and captures wall-clock. And
# because `claude -p` has no hard token cap and `recurve run --cap` bounds cycles
# not tokens, a TokenBudget accumulates per-cycle spend and stops the A3
# burndown at the cap — so A0 and A3 are matched on the budget, the experiment's
# key control. Hermetic: no live agent.
#
# RED until telemetry/budget exist. The trap prices an unpriced model and proves
# cost_usd refuses to return a silent $0.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.adapters.telemetry import cost_usd
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
try:
    cost_usd('a-model-with-no-price', 1000, 1000)
    print('SILENT')     # returned a number for an unpriced model → hazard
except KeyError:
    print('RAISED')     # refused to guess → guard holds
" 2>&1)" || { echo "telemetry incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^RAISED$'; then
    echo "cost_usd refuses to silently price an unknown model"; exit 1   # guard holds → RED
  fi
  echo "cost_usd silently priced an unknown model (fixture claimed it does)"; exit 0
fi

out="$(python3 -c "
import sys; sys.path.insert(0,'$EVAL')
try:
    from evallib.adapters.telemetry import parse_usage, cost_usd, wall_clock
    from evallib.budget import TokenBudget, run_capped
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# parse usage from an agent JSON report
assert parse_usage({'usage':{'input_tokens':100,'output_tokens':50}}) == (100, 50)
# cost from the dated table: 1M in + 1M out for Haiku = \$1 + \$5
assert abs(cost_usd('claude-haiku-4-5', 1_000_000, 1_000_000) - 6.0) < 1e-9
# budget enforcement: accumulate to the cap, then exhausted
b = TokenBudget(60000)
for _ in range(3): b.add(20000)
assert b.spent == 60000 and b.remaining() == 0 and b.exhausted()
# the A3 stop: cycles halt at the cap (6 cycles of 10k), bounded
n, spent = run_capped(60000, 10000)
assert n == 6 and spent == 60000, (n, spent)
# an over-cap cycle still stops within one cycle of the cap (cycle-granular)
n2, spent2 = run_capped(60000, 25000)
assert spent2 <= 60000 + 25000 and n2 == 3, (n2, spent2)
# a zero-token cycle cannot loop forever — it stops at the safety bound
n3, _ = run_capped(60000, 0, max_cycles=100)
assert n3 == 100, n3
# wall clock returns a non-negative elapsed
with wall_clock() as t: pass
assert t.elapsed >= 0.0
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "telemetry captures tokens/cost/wall-clock; TokenBudget enforces the cap (A3 halts at budget)"
  exit 0
fi
echo "ours=telemetry/budget wrong: $(printf '%s' "$out" | tail -1) oracle=usage+cost+wall-clock captured, cap enforced"
exit 1
