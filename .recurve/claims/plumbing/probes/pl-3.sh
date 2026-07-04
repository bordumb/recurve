#!/usr/bin/env bash
# PL-3: the burndown loop's stop decision consults the stopping controller —
# burndown.sh calls `recurve decide` on the cycle's measured gate vector and gates
# its success-halt on the verdict, instead of the cap/no-work watchdog deciding
# blind. This is the #4 wiring: the loop's verdict comes from controller.decide.
# RED-first: until burndown.sh calls decide the probe is RED; a workflow that
# computes a verdict but never branches on STOP-SUCCESS is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  WF="$TRAP_FIXTURE/burndown.sh"
else
  WF="$ROOT/templates/workflows/burndown.sh"
fi
[ -f "$WF" ] || { echo "no burndown.sh at $WF — cannot measure"; exit 2; }

# (a) it invokes the decide verb
if ! grep -qE '(\{\{PROG\}\}|\$PROG|\$\{PROG\}|recurve)[[:space:]]+decide' "$WF"; then
  echo "ours=burndown.sh never calls the decide verb oracle=the loop asks controller.decide for its stop verdict"
  exit 1
fi
# (b) the verdict drives the halt (branched on, not computed and ignored)
if ! grep -qE 'STOP-SUCCESS|STOP_SUCCESS' "$WF"; then
  echo "ours=burndown.sh calls decide but never branches on the verdict oracle=success-halt gated on STOP-SUCCESS"
  exit 1
fi
echo "burndown.sh consults recurve decide and gates its success-halt on the controller's verdict"
exit 0
