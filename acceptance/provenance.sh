#!/usr/bin/env bash
# Provenance hygiene: no ancestor vocabulary or origin-domain technology in
# anything the engine ships (recurvelib, the CLI, the schemas). recurve must
# read as if it had no first customer.
#
# This is the Phase 0 form of the standing probe the plan requires of the
# Phase 1 self-hosted suite (plan.md §14.1). The acceptance harness itself is
# exempt: it exists to point at the ancestors.
#
# Exit: 0 clean · 1 leakage found.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
RECURVE_DIR="$(dirname "$HERE")"

# Origin platform + domain technologies, ancestor tool/instance names, ancestor
# suite names, ancestor gap-ID prefixes, ancestor env vars. Domain acronyms
# that collide with English words (SAID) match case-sensitively.
PATTERNS_CI=(
  "auths" "keri" "keripy"
  "riclib" "rictl" "ictl" "interop" "ri-burndown" "flow-next"
  "lost-the-laptop" "faraday" "death-of-the-api-key"
  "pipeline-with-nothing" "verify-the-world"
  "AUTHS_SRC" "RI_PROBE"
)
PATTERNS_CS=(
  "\bSAID\b" "\bCESR\b" "\bKEL\b"
  "\bLTL-" "\bIOP-" "\bAITFC-" "\bV-WASM\b"
)

SHIPPED=("$RECURVE_DIR/recurvelib" "$RECURVE_DIR/recurve" "$RECURVE_DIR/schema"
         "$RECURVE_DIR/templates" "$RECURVE_DIR/packs")
# Optional override (used by the self-host trap to prove this probe can fail).
if [ "$#" -gt 0 ]; then SHIPPED=("$@"); fi

fail=0
scan() { # scan <grep-flags> <pattern>
  hits=$(grep -rn$1E "$2" "${SHIPPED[@]}" 2>/dev/null | grep -v "__pycache__")
  if [ -n "$hits" ]; then
    echo "LEAK: pattern '$2'"
    echo "$hits" | head -5
    fail=1
  fi
}
for pat in "${PATTERNS_CI[@]}"; do scan i "$pat"; done
for pat in "${PATTERNS_CS[@]}"; do scan "" "$pat"; done

if [ "$fail" -eq 0 ]; then
  echo "PROVENANCE OK — shipped engine carries no origin vocabulary"
fi
exit "$fail"
