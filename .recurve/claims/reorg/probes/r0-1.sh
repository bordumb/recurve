#!/usr/bin/env bash
# R0.1: the side-by-side differential harness — outputs and exit codes. It
# materializes the pinned pre-refactor engine (git archive of BASELINE_REF) and
# runs a fixed read-only roster (ledger, validate, matrix, matrix --gate, stats,
# trajectories, frontier, coverage, and the report --narrate error path) with
# BOTH the baseline and the working engine against identical fixture state,
# asserting byte-equal normalized stdout+stderr+exit. On an untouched tree the
# two engines are the same code, so the roster agrees (GREEN); any later phase
# that drifts turns this RED naming the first divergent command.
#
# GREEN by construction at arming (self ≡ baseline); falsified by the trap,
# which sabotages a baseline copy and proves the harness reports the divergence.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/_diff.sh"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  # Counterexample: a divergent engine. The harness MUST catch it (return RED).
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
  materialize_baseline "$T/base" || { echo "baseline unbuildable"; exit 2; }
  cp -R "$T/base" "$T/bad"
  # every invocation writes an extra stdout line — guaranteed divergence
  printf '\nimport sys as _s; _s.stdout.write("SABOTAGE\\n")\n' >> "$T/bad/recurvelib/__init__.py"
  build_fixture "$T/fix"; mkdir -p "$T/wd"
  if differential_readonly "$T/base" "$T/bad" "$T/fix" "$T/wd" >/dev/null 2>&1; then
    echo "harness missed a sabotaged engine (fixture claimed it does)"; exit 0
  fi
  echo "harness reports the sabotaged engine as divergent"; exit 1
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
materialize_baseline "$T/base" || { echo "pinned baseline missing or unbuildable — BROKEN, never a verdict"; exit 2; }

# Chrome is out of the contract by name (R0.4): the roster carries an
# engine-emitted error path and never --help or an unknown-command surface, so
# the later Typer phase is free to change that chrome while this stays green.
roster="$(diff_roster)"
printf '%s\n' "$roster" | grep -qx 'report --narrate' \
  || { echo "ours=roster omits the engine error path oracle=report --narrate is rostered"; exit 1; }
printf '%s\n' "$roster" | grep -qE '(^|[[:space:]])--help([[:space:]]|$)' \
  && { echo "ours=roster includes --help chrome oracle=help/unknown-command excluded by name"; exit 1; }

build_fixture "$T/fix"; mkdir -p "$T/wd"
if div="$(differential_readonly "$T/base" "$REPO" "$T/fix" "$T/wd")"; then
  echo "working engine ≡ pinned baseline across the read-only roster (outputs + exit codes)"
  exit 0
fi
echo "ours=\`$div\` diverges from the pinned baseline oracle=byte-equal normalized output + exit"
exit 1
