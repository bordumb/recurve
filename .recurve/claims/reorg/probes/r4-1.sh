#!/usr/bin/env bash
# R4.1 + R4.3 + R4.4: the flat modules regroup by concern into named
# subpackages. recurvelib/ holds a small set of concern subpackages (each with
# __init__.py) plus at most three loose modules — no misc/util junk-drawer;
# every internal import resolves (recurve validate runs); and
# recurvelib.resource_dir still finds the templates/schema/packs trees so init
# and schema loading keep working.
#
# RED against the pre-refactor flat layout (~35 loose modules); the trap points
# the scan at a flat/junk-drawer layout and proves it is rejected.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"

# scan_layout <recurvelib_root> — echoes the first fault, returns 1; 0 if the
# layout is a real concern-grouped package tree.
scan_layout() {
  local root="$1" loose subpkgs junk
  [ -d "$root" ] || { echo "no recurvelib dir"; return 1; }
  loose="$(find "$root" -maxdepth 1 -name '*.py' ! -name '__init__.py' | wc -l | tr -d ' ')"
  [ "$loose" -le 3 ] || { echo "$loose loose top-level modules (expected <=3)"; return 1; }
  subpkgs="$(find "$root" -mindepth 1 -maxdepth 1 -type d -exec test -f '{}/__init__.py' \; -print | wc -l | tr -d ' ')"
  [ "$subpkgs" -ge 3 ] || { echo "only $subpkgs subpackages (expected concern grouping)"; return 1; }
  junk="$(find "$root" -mindepth 1 -maxdepth 1 -type d \( -name misc -o -name util -o -name utils -o -name junk -o -name common -o -name helpers -o -name misc_ \) | head -1)"
  [ -z "$junk" ] || { echo "junk-drawer subpackage: $(basename "$junk")"; return 1; }
  return 0
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  mkdir -p "$W/recurvelib"
  : > "$W/recurvelib/__init__.py"
  i=0; while [ $i -lt 30 ]; do : > "$W/recurvelib/mod$i.py"; i=$((i+1)); done  # flat
  mkdir -p "$W/recurvelib/util"; : > "$W/recurvelib/util/__init__.py"          # junk-drawer
  if scan_layout "$W/recurvelib" >/dev/null 2>&1; then
    echo "scan accepted a flat + junk-drawer layout (fixture claimed it does)"; exit 0
  fi
  echo "scan rejects the flat/junk-drawer layout"; exit 1
fi

# structure
if fault="$(scan_layout "$REPO/recurvelib")"; then :; else
  echo "ours=$fault oracle=concern subpackages, <=3 loose modules, no junk-drawer"; exit 1
fi
# every internal import resolves — the engine runs
NO_COLOR=1 python3 "$REPO/recurve" validate >/dev/null 2>&1 \
  || { echo "ours=recurve validate fails after the regroup oracle=every internal import resolves"; exit 1; }
# resource_dir still finds the shipped trees (R4.4)
python3 -c "
import sys; sys.path.insert(0, '$REPO')
from recurvelib import resource_dir
for n in ('templates', 'schema', 'packs'):
    assert resource_dir(n).is_dir(), n
try:
    resource_dir('definitely-not-a-tree'); raise SystemExit('resource_dir did not fail loud')
except FileNotFoundError:
    pass
" 2>/dev/null \
  || { echo "ours=resource_dir broke on the regroup oracle=templates/schema/packs still resolve, bogus fails loud"; exit 1; }

echo "recurvelib regrouped into concern subpackages (<=3 loose, no junk-drawer); imports resolve; resource_dir intact"
exit 0
