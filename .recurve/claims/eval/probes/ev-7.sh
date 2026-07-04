#!/usr/bin/env bash
# EV-7: the A3 outcome classifier separates a *gate refusal* from a *process
# failure* — the distinction §4/§8.3 insist on. A run that authored a
# well-formed claim (a probe with a kept trap) but hit budget with a red gate
# is the gate doing its job (gate_refused). A run that never produced a
# well-formed claim/probe/trap is a harness-operation failure (process_failed),
# NOT the gate catching bad work — crediting the gate for it would make the
# weak model's numbers a lie. `classify_a3` reads the workspace's authored state
# and the gate verdict and returns declared / gate_refused / process_failed.
#
# RED until classify exists. The trap is a no-claim, red-gate workspace that a
# lazy classifier would miscredit as gate_refused; the guard must call it
# process_failed.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

MK='
import pathlib
def wellformed(ws):
    # a probe with a kept trap fixture — the agent operated the harness
    p = pathlib.Path(ws, "claims/s/probes"); p.mkdir(parents=True, exist_ok=True)
    (p/"g-1.sh").write_text("#!/bin/sh\nexit 0\n")
    t = p/"g-1.trap"/"curated"; t.mkdir(parents=True, exist_ok=True)
    (t/"x").write_text("counterexample\n")
def barren(ws):
    # recurve-init-ish shell, but no probe+trap ever authored
    pathlib.Path(ws, "claims/s/probes").mkdir(parents=True, exist_ok=True)
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  out="$(python3 -c "
import sys, tempfile; sys.path.insert(0,'$EVAL')
try:
    from evallib.classify import classify_a3
except Exception as e:
    print('incomplete:', e); raise SystemExit(2)
$MK
ws = tempfile.mkdtemp(); barren(ws)            # no well-formed claim...
label = classify_a3(ws, gate_green=False)      # ...and a red gate
print(label)
" 2>&1)" || { echo "classify incomplete: $out"; exit 2; }
  if printf '%s\n' "$out" | grep -q '^process_failed$'; then
    echo "classify_a3 calls a no-claim red-gate run process_failed"; exit 1   # guard holds → RED
  fi
  echo "classify_a3 miscredited a process failure as $out (fixture claimed it does)"; exit 0
fi

out="$(python3 -c "
import sys, tempfile; sys.path.insert(0,'$EVAL')
try:
    from evallib.classify import classify_a3, has_wellformed_claim
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
$MK
d=tempfile.mkdtemp(); wellformed(d); assert classify_a3(d, gate_green=True)=='declared'
r=tempfile.mkdtemp(); wellformed(r); assert classify_a3(r, gate_green=False)=='gate_refused'
p=tempfile.mkdtemp(); barren(p);    assert classify_a3(p, gate_green=False)=='process_failed'
# even a (nonsensical) green gate with no authored claim is a process failure, not a solve
p2=tempfile.mkdtemp(); barren(p2);  assert classify_a3(p2, gate_green=True)=='process_failed'
assert has_wellformed_claim(d) and not has_wellformed_claim(p)
print('OK')
" 2>&1)"
if printf '%s\n' "$out" | grep -q '^OK$'; then
  echo "classify_a3 splits declared / gate_refused / process_failed by authored state + gate"
  exit 0
fi
echo "ours=classify wrong: $(printf '%s' "$out" | tail -1) oracle=gate-refusal vs process-failure separated"
exit 1
