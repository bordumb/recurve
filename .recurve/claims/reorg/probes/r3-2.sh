#!/usr/bin/env bash
# R3.3: captured output carries no framework color or chrome. Under a pipe or
# with NO_COLOR set, the CLI emits no ANSI styling into stdout or stderr, so
# captured and piped output stays plain for the probes that read it — Typer
# must not leak color into help, errors, or command output.
#
# GREEN now (argparse emits none) and must survive the Typer swap. The trap
# feeds the detector sample output containing an ANSI escape and proves it is
# flagged.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"

# has_ansi <file> — 0 if the file contains an ESC[ CSI sequence, 1 otherwise.
has_ansi() { LC_ALL=C grep -q "$(printf '\033')\\[" "$1"; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  printf 'plain line\n\033[31mred chrome\033[0m\n' > "$W/sample"
  if has_ansi "$W/sample"; then
    echo "detector flags ANSI in captured output"; exit 1
  fi
  echo "detector missed an ANSI escape (fixture claimed it does)"; exit 0
fi

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
# capture help, an unknown-command error, and a real command under a pipe + NO_COLOR
NO_COLOR=1 python3 "$REPO/recurve" --help                > "$T/help" 2>&1 | cat
NO_COLOR=1 python3 "$REPO/recurve" --help                > "$T/help" 2>&1
NO_COLOR=1 python3 "$REPO/recurve" definitely-not-a-cmd  > "$T/bad"  2>&1
NO_COLOR=1 python3 "$REPO/recurve" demo                  > "$T/demo" 2>&1
for f in help bad demo; do
  if has_ansi "$T/$f"; then
    echo "ours=ANSI escape leaked into captured \`$f\` output oracle=plain under pipe/NO_COLOR"; exit 1
  fi
done
echo "no ANSI color or chrome leaks into piped/captured output (help, errors, and a real command)"
exit 0
