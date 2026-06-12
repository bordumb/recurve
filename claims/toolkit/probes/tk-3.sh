#!/usr/bin/env bash
# TK-3: the verdict map is total (crash/signal/timeout → BROKEN, never a
# verdict) and records/receipts validate structurally.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  python3 "$TRAP_FIXTURE/lenient_map_check.py"
else
  python3 "$ROOT/acceptance/selfcheck.py" >/dev/null 2>&1
fi
case "$?" in
  0) echo "verdict map total; records and receipts validate"; exit 0 ;;
  1) echo "ours=a crash read as a verdict oracle=anything but 0/1 is BROKEN"; exit 1 ;;
  *) echo "selfcheck could not run"; exit 2 ;;
esac
