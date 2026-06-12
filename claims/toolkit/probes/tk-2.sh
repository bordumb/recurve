#!/usr/bin/env bash
# TK-2: live-equivalent to both ancestor instances (fast subset — the full
# probe-running comparison is acceptance/diff.sh without --fast).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export RECURVE_ACCEPT="$ROOT/acceptance"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  export RUN_HELPER="bash $TRAP_FIXTURE/run_helper.sh"
fi
OUT="$(bash "$ROOT/acceptance/diff.sh" --fast 2>&1)"
case "$?" in
  0) echo "live-equivalent to both ancestors (fast subset)"; exit 0 ;;
  3) echo "ancestor instances not present at this checkout — cannot measure"; exit 2 ;;
  1) echo "ours=divergence oracle=byte-identical — $(printf '%s' "$OUT" | grep FAIL | head -1)"; exit 1 ;;
  *) echo "comparison harness failed to run"; exit 2 ;;
esac
