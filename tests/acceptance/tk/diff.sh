#!/usr/bin/env bash
# Phase 0 acceptance: the migration IS the test suite.
#
# LIVE side-by-side: every command runs through BOTH the preserved original
# implementations (the ancestor CLIs, untouched in their repos) and the
# recurve engine (via configs/ + run.py, read-only against the same trees),
# at the same moment, and the outputs are diffed byte-for-byte. A static
# golden snapshot would rot whenever the ancestors' own loops advance their
# ledgers; a live diff cannot.
#
# Two documented waivers: the second instance's hand-rolled `validate` and
# `coverage` renderings were canonicalized (same facts, fuller format) — for
# those, facts are compared, not bytes.
#
# The ancestor-facing fixtures (ancestors.env, configs/, golden/, originals/)
# are LOCAL-ONLY and untracked — see acceptance/LOCAL.md.
#
# Usage: acceptance/diff.sh [--fast]   (--fast skips the probe-running matrix steps)
# Exit:  0 equivalent · 1 divergence · 3 ancestors not present (cannot compare)

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"          # recurve/acceptance
FAST=0
[ "${1:-}" = "--fast" ] && FAST=1
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The ancestor instances are LOCAL-ONLY fixtures (see acceptance/LOCAL.md):
# ancestors.env (untracked) names the original CLIs and their program names.
# Without it — any checkout away from the origin workspace — there is nothing
# to compare against, and that is a SKIP, never a verdict.
ENV_FILE="$HERE/ancestors.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "SKIP: no acceptance/ancestors.env — ancestor instances not configured at this checkout."
  exit 3
fi
. "$ENV_FILE"   # ORIG_A_CLI, ORIG_B_CLI, PROG_A, PROG_B
if [ ! -x "${ORIG_A_CLI:-}" ] || [ ! -x "${ORIG_B_CLI:-}" ]; then
  echo "SKIP: ancestor instances not present at this checkout — nothing to compare against."
  exit 3
fi

# RUN_HELPER override exists so the self-host trap can prove this harness can
# fail (it wraps the engine and corrupts its output; the diff must catch it).
RUNNER="${RUN_HELPER:-python3 $HERE/run.py}"
ri()  { $RUNNER demos "$PROG_A" "$@"; }
i()   { $RUNNER conformance "$PROG_B" "$@"; }
ori() { "$ORIG_A_CLI" "$@"; }
oi()  { "$ORIG_B_CLI" "$@"; }

fail=0
check_live() { # check_live <label> <orig-fn> <engine-fn> <args...>
  local label="$1" ofn="$2" efn="$3"; shift 3
  "$ofn" "$@" > "$TMP/o" 2>&1
  local orc=$?
  "$efn" "$@" > "$TMP/e" 2>&1
  local erc=$?
  if diff -q "$TMP/o" "$TMP/e" >/dev/null 2>&1 && [ "$orc" -eq "$erc" ]; then
    echo "  ok   $label"
  else
    echo "  FAIL $label (orig exit $orc, engine exit $erc)"
    diff "$TMP/o" "$TMP/e" | head -8
    fail=1
  fi
}

echo "instance 1 (demo loop): original $PROG_A vs engine, live"
for c in ledger validate next coverage freshness; do
  check_live "$PROG_A $c" ori ri "$c"
done
FIRST="$(ori ledger | grep -oE '^[A-Z][A-Z0-9]*-[A-Za-z0-9]+' | head -1)"
[ -n "$FIRST" ] && check_live "$PROG_A show $FIRST" ori ri show "$FIRST"
if [ "$FAST" -eq 0 ]; then
  check_live "$PROG_A matrix" ori ri matrix
  ori matrix --gate >/dev/null 2>&1; orc=$?
  ri matrix --gate >/dev/null 2>&1; erc=$?
  if [ "$orc" -eq "$erc" ]; then echo "  ok   $PROG_A matrix --gate exit ($orc)"; else
    echo "  FAIL $PROG_A matrix --gate exit (orig $orc engine $erc)"; fail=1; fi
fi

echo "instance 2 (conformance): original $PROG_B vs engine, live"
for c in ledger freshness; do
  check_live "$PROG_B $c" oi i "$c"
done
FIRSTI="$(oi ledger | grep -oE '^[A-Z][A-Z0-9]*-[A-Za-z0-9]+' | head -1)"
[ -n "$FIRSTI" ] && check_live "$PROG_B show $FIRSTI" oi i show "$FIRSTI"
# Waived renderings: compare the FACTS (gap count; orphan count), not bytes.
ON="$(oi validate | grep -oE '[0-9]+ gaps parsed' | head -1)"
EN="$(i validate | grep -oE '[0-9]+ gaps parsed' | head -1)"
if [ -n "$ON" ] && [ "$ON" = "$EN" ]; then echo "  ok   $PROG_B validate (canonicalized; facts match: $ON)"; else
  echo "  FAIL $PROG_B validate facts (orig '$ON' engine '$EN')"; fail=1; fi
OO="$(oi coverage | grep -oE '^[0-9]+ orphan' | head -1)"
EO="$(i coverage | grep -oE '^[0-9]+ orphan' | head -1)"
if [ -n "$OO" ] && [ "$OO" = "$EO" ]; then echo "  ok   $PROG_B coverage (canonicalized; facts match: $OO)"; else
  echo "  FAIL $PROG_B coverage facts (orig '$OO' engine '$EO')"; fail=1; fi
if [ "$FAST" -eq 0 ]; then
  check_live "$PROG_B matrix" oi i matrix
  oi matrix --gate >/dev/null 2>&1; orc=$?
  i matrix --gate >/dev/null 2>&1; erc=$?
  if [ "$orc" -eq "$erc" ]; then echo "  ok   $PROG_B matrix --gate exit ($orc)"; else
    echo "  FAIL $PROG_B matrix --gate exit (orig $orc engine $erc)"; fail=1; fi
fi

echo "engine self-checks:"
if python3 "$HERE/selfcheck.py" > "$TMP/selfcheck" 2>&1; then
  echo "  ok   records + probe contract selfcheck"
else
  echo "  FAIL records + probe contract selfcheck"; cat "$TMP/selfcheck"; fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "ACCEPTANCE OK — engine is live-equivalent to both ancestors (2 documented waivers)"
else
  echo "ACCEPTANCE FAILED"
fi
exit "$fail"
