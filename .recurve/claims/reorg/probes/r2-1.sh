#!/usr/bin/env bash
# R2.1 + R2.2: cli.py becomes a package (argparse intact), and the console
# entrypoint survives. recurvelib/cli.py is no longer a single module;
# recurvelib/cli/ is a package holding main.py plus one module per command
# under commands/, with no file exceeding 400 lines — and recurvelib.cli:main
# stays importable so the `recurve` console script and repo wrapper still
# dispatch. Behavioral inertness (R2.3) is enforced by the standing R0/R1
# guards the fleet gate runs; this probe owns the structure and the entrypoint.
#
# RED until the split lands. The trap points the structural scan at a cli/ that
# relocated the monolith (a single oversized module) and proves it is rejected.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"

# scan_structure <cli_root> — echoes the first structural fault and returns 1;
# returns 0 if the layout is a real split (package + main.py + commands/, no
# file over 400 lines, at least 20 command modules).
scan_structure() {
  local root="$1" n big
  [ -d "$root" ] || { echo "no cli/ package dir"; return 1; }
  [ -f "$root/__init__.py" ] || { echo "cli/ missing __init__.py"; return 1; }
  [ -f "$root/main.py" ] || { echo "cli/ missing main.py"; return 1; }
  [ -d "$root/commands" ] || { echo "cli/ missing commands/ dir"; return 1; }
  n="$(find "$root/commands" -maxdepth 1 -name '*.py' ! -name '__init__.py' | wc -l | tr -d ' ')"
  [ "$n" -ge 20 ] || { echo "only $n command modules (expected one per command)"; return 1; }
  big="$(find "$root" -name '*.py' -exec awk 'END{if(NR>400)print FILENAME" ("NR" lines)"}' {} \; | head -1)"
  [ -z "$big" ] || { echo "file over 400 lines: $big"; return 1; }
  return 0
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  # a cli/ that relocated the monolith: package shell present, but one command
  # module carries the whole 1586-line bulk.
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  mkdir -p "$W/cli/commands"
  : > "$W/cli/__init__.py"; : > "$W/cli/main.py"
  i=0; while [ $i -lt 25 ]; do : > "$W/cli/commands/c$i.py"; i=$((i+1)); done
  awk 'BEGIN{for(i=0;i<1586;i++)print "# relocated monolith line "i}' > "$W/cli/commands/everything.py"
  if scan_structure "$W/cli" >/dev/null 2>&1; then
    echo "structural scan accepted a relocated monolith (fixture claimed it does)"; exit 0
  fi
  echo "structural scan rejects the relocated monolith"; exit 1
fi

# structure
if [ -f "$REPO/recurvelib/cli.py" ]; then
  echo "ours=recurvelib/cli.py is still a single module oracle=recurvelib/cli/ is a package"; exit 1
fi
if fault="$(scan_structure "$REPO/recurvelib/cli")"; then :; else
  echo "ours=$fault oracle=cli/ package with main.py + one module per command, none over 400 lines"; exit 1
fi

# entrypoint: recurvelib.cli:main importable and callable
python3 -c "import sys; sys.path.insert(0, '$REPO'); from recurvelib.cli import main; assert callable(main)" 2>/dev/null \
  || { echo "ours=recurvelib.cli:main no longer resolves oracle=the console entrypoint survives the split"; exit 1; }
# the wrapper still dispatches
NO_COLOR=1 python3 "$REPO/recurve" --help >/dev/null 2>&1 \
  || { echo "ours=recurve --help does not run oracle=the repo wrapper dispatches every command"; exit 1; }

echo "cli.py split into a package (main.py + one module per command, none over 400 lines); recurvelib.cli:main survives"
exit 0
