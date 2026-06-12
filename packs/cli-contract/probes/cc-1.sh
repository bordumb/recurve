#!/usr/bin/env bash
# CC-1: --help prints usage and exits 0.  Configure: PACK_CLI=<command>
if [ -n "${TRAP_FIXTURE:-}" ]; then
  CLI="bash $TRAP_FIXTURE/cli.sh"
elif [ -z "${PACK_CLI:-}" ]; then
  echo "PACK_CLI not set — cannot measure"; exit 2
else
  CLI="$PACK_CLI"
fi
OUT="$($CLI --help 2>&1)"; RC=$?
if [ $RC -ne 0 ]; then echo "ours=exit:$RC oracle=exit:0 on --help"; exit 1; fi
if ! printf '%s' "$OUT" | grep -qiE 'usage|options'; then
  echo "ours=no usage/options section oracle=help text names its surface"; exit 1
fi
echo "help contract holds"; exit 0
