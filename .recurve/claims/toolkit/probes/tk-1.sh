#!/usr/bin/env bash
# TK-1: no origin vocabulary ships. The one legitimate source grep here —
# the claim is ABOUT source. TRAP_FIXTURE scans a salted module instead.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  bash "$ROOT/tests/acceptance/tk/provenance.sh" "$TRAP_FIXTURE" >/dev/null 2>&1
else
  bash "$ROOT/tests/acceptance/tk/provenance.sh" >/dev/null 2>&1
fi
case "$?" in
  0) echo "shipped surface carries no origin vocabulary"; exit 0 ;;
  1) echo "ours=origin vocabulary found oracle=none across engine/CLI/schema/templates/packs"; exit 1 ;;
  *) echo "provenance scan could not run"; exit 2 ;;
esac
