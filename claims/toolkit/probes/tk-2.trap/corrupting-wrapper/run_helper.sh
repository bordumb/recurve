#!/usr/bin/env bash
# Counterexample: an engine whose output is corrupted in flight. The live
# diff MUST catch it.
python3 "$RECURVE_ACCEPT/run.py" "$@" | sed 's/gap/gxp/g'
exit "${PIPESTATUS[0]}"
