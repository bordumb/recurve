#!/usr/bin/env bash
# EV-7: the A3 outcome classifier separates a genuine gate refusal from a
# process failure — and that turns on the TERMINAL RUN-STATE (why the run
# ended), which lives in telemetry, not the workspace. `classify_gated_run(workspace,
# terminal_state)` reads both. Boundaries, all pinned:
#   no well-formed claim ever authored        -> process_failed
#   gate BROKEN (a probe could not decide)     -> process_failed
#   gate GREEN                                 -> declared
#   gate RED, ended on budget exhaustion        -> gate_refused
#   gate RED, ended on a crash/error            -> process_failed
# Crediting any process failure to the gate would corrupt the headline
# decomposition (refusals are where the weak model's delta is predicted to
# live), so each boundary carries its own trap.
#
# RED until classify exists. Each trap asserts a would-be-miscredited case is
# classified process_failed, never gate_refused.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

MK='
import pathlib
def wellformed(ws):
    p = pathlib.Path(ws, "claims/s/probes"); p.mkdir(parents=True, exist_ok=True)
    (p/"g-1.sh").write_text("#!/bin/sh\nexit 0\n")
    t = p/"g-1.trap"/"curated"; t.mkdir(parents=True, exist_ok=True)
    (t/"x").write_text("counterexample\n")
def barren(ws):
    pathlib.Path(ws, "claims/s/probes").mkdir(parents=True, exist_ok=True)
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  scenario="$(cat "$TRAP_FIXTURE/scenario" 2>/dev/null || echo no_claim)"
  out="$(python3 -c "
import sys, tempfile; sys.path.insert(0,'$EVAL')
try:
    from evallib.classify import classify_gated_run
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
$MK
sc='$scenario'
ws=tempfile.mkdtemp()
if sc=='no_claim':
    barren(ws);  ts={'gate':'red','stop_reason':'budget_exhausted'}
elif sc=='broken':
    wellformed(ws); ts={'gate':'broken','stop_reason':'budget_exhausted'}
elif sc=='crashed':
    wellformed(ws); ts={'gate':'red','stop_reason':'crashed'}
else:
    barren(ws); ts={'gate':'red','stop_reason':'budget_exhausted'}
print(classify_gated_run(ws, ts))
" 2>&1)" || { echo "classify incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^process_failed$'; then
    echo "classify_gated_run classifies the '$scenario' boundary as process_failed, not gate_refused"; exit 1
  fi
  echo "classify_gated_run miscredited '$scenario' as $out (fixture claimed it does)"; exit 0
fi

out="$(python3 -c "
import sys, tempfile; sys.path.insert(0,'$EVAL')
try:
    from evallib.classify import classify_gated_run, has_wellformed_claim
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
$MK
def cls(build, ts):
    d=tempfile.mkdtemp(); build(d); return classify_gated_run(d, ts)
assert cls(wellformed, {'gate':'green','stop_reason':'gate_green'})           == 'declared'
assert cls(wellformed, {'gate':'red','stop_reason':'budget_exhausted'})       == 'gate_refused'
assert cls(wellformed, {'gate':'broken','stop_reason':'budget_exhausted'})    == 'process_failed'   # BROKEN boundary
assert cls(wellformed, {'gate':'red','stop_reason':'crashed'})                == 'process_failed'   # red-but-crashed
assert cls(barren,     {'gate':'red','stop_reason':'budget_exhausted'})       == 'process_failed'   # no claim
assert cls(barren,     {'gate':'green','stop_reason':'gate_green'})           == 'process_failed'   # green over no claim
d=tempfile.mkdtemp(); wellformed(d); assert has_wellformed_claim(d)
p=tempfile.mkdtemp(); barren(p);    assert not has_wellformed_claim(p)
print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=classify wrong: $(printf '%s' "$out"|tail -1) oracle=refusal/process-failure separated across all boundaries"; exit 1; }
echo "classify_gated_run splits declared / gate_refused / process_failed from (workspace, terminal_state) at every boundary"
exit 0
