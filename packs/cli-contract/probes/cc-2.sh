#!/usr/bin/env bash
# CC-2: an unknown flag exits nonzero with an error on stderr.
if [ -n "${TRAP_FIXTURE:-}" ]; then
  CLI="bash $TRAP_FIXTURE/cli.sh"
elif [ -z "${PACK_CLI:-}" ]; then
  echo "PACK_CLI not set — cannot measure"; exit 2
else
  CLI="$PACK_CLI"
fi
ERR="$($CLI --definitely-not-a-real-flag-xyz 2>&1 >/dev/null)"; RC=$?
if [ $RC -eq 0 ]; then echo "ours=exit:0 oracle=nonzero (a CLI that accepts anything confirms nothing)"; exit 1; fi
if [ -z "$ERR" ]; then echo "ours=silent failure oracle=error text on stderr"; exit 1; fi
echo "unknown flags rejected loudly"; exit 0
