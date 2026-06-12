#!/usr/bin/env bash
# TK-8: an orchestrator can hold the tree lock across CLI invocations:
# acquire / refused-while-held / release / re-acquire. RED-first: a missing
# surface is RED.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -n "${TRAP_FIXTURE:-}" ]; then
  CLI() { bash "$TRAP_FIXTURE/permissive-cli.sh" "$@"; }
else
  CLI() { python3 "$ROOT/recurve" "$@"; }
fi
T="$(mktemp -d)"
trap 'CLI --config "$T/recurve.toml" lock release >/dev/null 2>&1; rm -rf "$T"' EXIT
cat > "$T/recurve.toml" <<EOF
[project]
name = "x"
default_reads = "none"
[target]
tree = "."
[reads.none]
method = "none"
[suites.s]
dir = "."
EOF
CLI --config "$T/recurve.toml" lock acquire >/dev/null 2>&1 \
  || { echo "ours=no acquire surface oracle=lock acquire/release for orchestrators"; exit 1; }
if CLI --config "$T/recurve.toml" lock acquire >/dev/null 2>&1; then
  echo "ours=second acquire granted oracle=refused while held (two loops corrupt one tree)"
  exit 1
fi
CLI --config "$T/recurve.toml" lock release >/dev/null 2>&1 \
  || { echo "ours=no release surface oracle=explicit release"; exit 1; }
CLI --config "$T/recurve.toml" lock acquire >/dev/null 2>&1 \
  || { echo "ours=re-acquire after release refused oracle=clean handoff"; exit 1; }
CLI --config "$T/recurve.toml" lock release >/dev/null 2>&1
echo "lock holds across invocations; refusal and release behave"
exit 0
