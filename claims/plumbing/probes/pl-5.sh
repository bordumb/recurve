#!/usr/bin/env bash
# PL-5: the loop feeds the FULL measured vector to the controller — burndown.sh
# sources the vector via `recurve sense` and passes --uncovered and --divergent to
# `recurve decide`, so an uncovered frontier or a divergence blocks STOP-SUCCESS,
# not just the gate counts. RED-first: a stop decision carrying only
# --open/--regressed/--broken (dropping uncovered + divergent) is RED.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  WF="$TRAP_FIXTURE/burndown.sh"
else
  WF="$ROOT/templates/workflows/burndown.sh"
fi
[ -f "$WF" ] || { echo "no burndown.sh at $WF — cannot measure"; exit 2; }

miss=""
grep -qE '(\{\{PROG\}\}|\$PROG|\$\{PROG\}|recurve)[[:space:]]+sense' "$WF" || miss="$miss recurve-sense"
grep -qE -- '--uncovered' "$WF" || miss="$miss --uncovered"
grep -qE -- '--divergent' "$WF" || miss="$miss --divergent"
if [ -n "$miss" ]; then
  echo "ours=burndown.sh stop vector omits:$miss oracle=decide fed --uncovered + --divergent sourced from recurve sense"
  exit 1
fi
echo "the loop sources the full vector via recurve sense and feeds --uncovered + --divergent to the controller"
exit 0
