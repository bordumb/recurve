#!/usr/bin/env bash
# R1: the golden characterization harness — the guardian that outlives R0's
# pin. R0 dies with the migration (its baseline ref retires once the reorg
# lands); R1 pins the observable contract durably, as captured golden bytes per
# command, so any FUTURE change that shifts real-invocation output turns RED.
# Same read-only roster as R0, same chrome exclusion, but anchored to recorded
# bytes instead of a reference engine. Covers PRD R1.1 and R1.2.
#
# GREEN when every rostered command matches its golden; a missing golden is
# BROKEN (never a silent pass). The trap corrupts a golden copy and proves the
# comparison is real — it flags the mismatch rather than waving it through.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/_diff.sh"
GOLDEN_DIR="${GOLDEN_DIR:-$DIR/../golden}"

slug() { printf '%s' "$1" | tr ' /' '__'; }

# compare_to_goldens <golden_dir> — run the roster against a fresh fixture and
# compare each command's normalized transcript to its golden. Echoes the first
# drifted command and returns 1; returns 2 if a golden is missing; 0 if all match.
compare_to_goldens() {
  local gdir="$1" fix wd i line s rc=0
  fix="$(mktemp -d)"; build_fixture "$fix"; wd="$(mktemp -d)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    s="$gdir/$(slug "$line").txt"
    if [ ! -f "$s" ]; then echo "missing golden: $line"; rc=2; break; fi
    # shellcheck disable=SC2086
    capture "$REPO" "$fix" "$wd/cur" $line
    if ! cmp -s "$wd/cur" "$s"; then echo "$line"; rc=1; break; fi
  done <<ROS
$(diff_roster)
ROS
  rm -rf "$fix" "$wd"; return $rc
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  G="$(mktemp -d)"; trap 'rm -rf "$G"' EXIT
  cp "$GOLDEN_DIR"/*.txt "$G"/ 2>/dev/null || { echo "no goldens captured yet"; exit 2; }
  printf 'CORRUPTED\n' >> "$(ls "$G"/*.txt | head -1)"
  if compare_to_goldens "$G" >/dev/null 2>&1; then
    echo "comparison passed a corrupted golden (fixture claimed it does)"; exit 0
  fi
  echo "comparison flags the corrupted golden"; exit 1
fi

# Chrome excluded by name (R1.2), same as R0.
roster="$(diff_roster)"
printf '%s\n' "$roster" | grep -qx 'report --narrate' \
  || { echo "ours=roster omits the engine error path oracle=report --narrate is rostered"; exit 1; }
printf '%s\n' "$roster" | grep -qE '(^|[[:space:]])--help([[:space:]]|$)' \
  && { echo "ours=roster includes --help chrome oracle=help/unknown-command excluded by name"; exit 1; }

drift="$(compare_to_goldens "$GOLDEN_DIR")"; rc=$?
case "$rc" in
  0) echo "every read-only roster command matches its captured golden"; exit 0 ;;
  2) echo "$drift — BROKEN (regenerate goldens with a reviewed capture)"; exit 2 ;;
  *) echo "ours=\`$drift\` drifted from its captured golden oracle=byte-equal normalized output + exit"; exit 1 ;;
esac
