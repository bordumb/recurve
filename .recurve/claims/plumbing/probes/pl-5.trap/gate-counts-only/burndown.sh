#!/usr/bin/env bash
# BROKEN counterexample for PL-5: the loop's stop decision carries only the gate
# counts — it calls decide with --open/--regressed/--broken and never sources the
# completeness (uncovered) or fidelity (divergent) signal. An uncovered frontier or
# a diverged build could then be called STOP-SUCCESS.
set -u
PROG="recurve"
stop_verdict() {
  $PROG decide --open "${1:-0}" --regressed "${2:-0}" --broken "${3:-0}"
}
stop_verdict 0 0 0
