#!/usr/bin/env bash
# R4.2: probe imports move in the same change. Every probe and trap fixture that
# imported a moved module now names its new subpackage path — no probe or
# fixture under the claims tree still imports a retired flat `recurvelib.<mod>`
# path. Updating an import to follow a moved module is maintenance, not
# weakening: the fleet gate plus every trap re-prove RED after it (enforced by
# the gate, not this probe).
#
# GREEN when no retired flat import remains. The trap plants a fixture importing
# `recurvelib.controller` (a retired flat path) and proves the scan flags it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"

MODS='model|probe|conformance|freshness|baseline|config|run|controller|runtime|adapters|lock|cycle|parked|demo|records|receipts|pack|importer|report|render|init|status|adjudicate|triage|frontier|frontier_cli|coverage|completeness|measured|surface|admission|claimify|fidelity|sense_cli|decide_cli'

# retired_refs <root> — echo .sh/.py files whose IMPORT statements still name a
# retired flat recurvelib.<mod> path (a moved module directly under recurvelib,
# not under its new subpackage). Prose/comments are not imports and are ignored;
# this probe's own file is excluded (it lists module names in its trap).
retired_refs() {
  local root="$1" f
  while IFS= read -r f; do
    case "$f" in */reorg/probes/r4-2.sh) continue ;; esac
    # The trailing alternation requires a true LEAF reference (whitespace or
    # end of line right after the module name) — `recurvelib.adapters.snapshot`
    # (a NEW subpackage, docs/plans/ablation-infra.md) must NOT match just
    # because it shares a prefix with the OLD retired flat `recurvelib.adapters`
    # module; only a bare `recurvelib.adapters` (no further `.subpath`) does.
    grep -qE "(from|import)[[:space:]]+recurvelib\.($MODS)([[:space:]]|\$)" "$f" 2>/dev/null && printf '%s\n' "$f"
  done < <(find "$root" \( -name '*.sh' -o -name '*.py' \) 2>/dev/null)
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  mkdir -p "$W/probes"
  # build the retired path dynamically so this probe carries no literal to self-match
  printf 'from recurvelib.%s import decide\n' controller > "$W/probes/leftover.py"
  if [ -z "$(retired_refs "$W")" ]; then
    echo "scan missed a retired flat import (fixture claimed it does)"; exit 0
  fi
  echo "scan flags the retired flat import"; exit 1
fi

hits="$(retired_refs "$REPO/.recurve/claims")"
if [ -n "$hits" ]; then
  echo "ours=probes still import retired flat paths oracle=every import follows the move:"
  printf '%s\n' "$hits" | sed 's#^#  #' | head -8
  exit 1
fi
echo "no probe or fixture under the claims tree imports a retired flat recurvelib.<mod> path"
exit 0
