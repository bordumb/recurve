#!/usr/bin/env bash
# BROKEN counterexample for PL-3: calls the decide verb but never branches on its
# verdict — the controller is consulted for show while the cap watchdog still
# decides when the loop is done. Wiring decide is meaningless if the verdict is
# computed and thrown away.
set -u
PROG="recurve"
CAP="${CAP:-12}"
cycle=0
$PROG decide --open 0 >/dev/null 2>&1   # computed and discarded
while [ "$cycle" -lt "$CAP" ]; do
  cycle=$((cycle + 1))
done
echo "cap reached"
