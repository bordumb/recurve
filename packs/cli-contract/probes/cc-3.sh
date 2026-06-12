#!/usr/bin/env bash
# CC-3: --version prints a dotted version and exits 0.
if [ -n "${TRAP_FIXTURE:-}" ]; then
  CLI="bash $TRAP_FIXTURE/cli.sh"
elif [ -z "${PACK_CLI:-}" ]; then
  echo "PACK_CLI not set — cannot measure"; exit 2
else
  CLI="$PACK_CLI"
fi
OUT="$($CLI --version 2>&1)"; RC=$?
if [ $RC -ne 0 ]; then echo "ours=exit:$RC oracle=exit:0 on --version"; exit 1; fi
if ! printf '%s' "$OUT" | grep -qE '[0-9]+\.[0-9]+'; then
  echo "ours=${OUT:-empty} oracle=a dotted version number"; exit 1
fi
echo "version contract holds"; exit 0
