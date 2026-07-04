#!/usr/bin/env bash
# R3.1: Typer is the dispatcher and a declared dependency. The CLI layer
# dispatches through Typer with no `import argparse` anywhere under
# recurvelib/cli/, and `typer` is declared in pyproject.toml dependencies, so a
# fresh install resolves and runs the recurve entrypoint. The command bodies are
# unchanged — only the dispatch/argument-declaration layer moves.
#
# RED until the swap lands (argparse still dispatches). The trap points the scan
# at a cli/ that imports typer but leaves argparse dispatching (imported but
# unused) and proves it is rejected.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"

# scan_dispatch <cli_root> — echoes the first fault, returns 1; 0 if Typer is the
# dispatcher (imports typer, no argparse import anywhere under the package).
scan_dispatch() {
  local root="$1"
  grep -rqE '^\s*(import|from)\s+typer' "$root" 2>/dev/null \
    || { echo "no typer import under cli/"; return 1; }
  if grep -rnE '^\s*import\s+argparse|^\s*from\s+argparse' "$root" 2>/dev/null | grep -q .; then
    echo "argparse still imported under cli/"; return 1
  fi
  return 0
}

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
  mkdir -p "$W/cli"
  printf 'import typer\n' > "$W/cli/main.py"          # typer imported...
  printf 'import argparse\n' >> "$W/cli/main.py"      # ...but argparse still dispatches
  if scan_dispatch "$W/cli" >/dev/null 2>&1; then
    echo "scan accepted argparse-with-typer-imported (fixture claimed it does)"; exit 0
  fi
  echo "scan rejects a cli/ that keeps argparse dispatching"; exit 1
fi

# dispatcher: typer in, argparse out (under cli/)
if fault="$(scan_dispatch "$REPO/recurvelib/cli")"; then :; else
  echo "ours=$fault oracle=Typer dispatches, no argparse under cli/"; exit 1
fi
# typer declared as a runtime dependency (parse the actual dependencies list —
# format-agnostic, single- or multi-line)
python3 - "$REPO/pyproject.toml" <<'PY' || { echo "ours=typer not in pyproject dependencies oracle=typer is a declared runtime dep"; exit 1; }
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
deps = d.get("project", {}).get("dependencies", [])
sys.exit(0 if any(str(x).lower().startswith("typer") for x in deps) else 1)
PY
# the entrypoint still resolves and dispatches a real command
python3 -c "import sys; sys.path.insert(0,'$REPO'); from recurvelib.cli import main; assert callable(main)" 2>/dev/null \
  || { echo "ours=recurvelib.cli:main broke under the swap oracle=entrypoint survives"; exit 1; }
NO_COLOR=1 python3 "$REPO/recurve" --help >/dev/null 2>&1 \
  || { echo "ours=recurve --help fails under Typer oracle=the entrypoint runs"; exit 1; }

echo "Typer is the dispatcher (no argparse under cli/), declared in pyproject, entrypoint intact"
exit 0
