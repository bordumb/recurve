#!/usr/bin/env bash
# SW-8: the harness commits the current working-tree state itself, right
# before the governor is consulted -- never relying on the agent to have
# committed anything. Found running the REAL smoke: all 6 A9 cells showed
# declared_done=False/gate_outcome=process_failed UNIFORMLY, regardless of
# whether the underlying fix was actually correct, because `build_cycle_
# snapshot(tree, "HEAD", ...)` refuses on ANY uncommitted change
# (snapshot.py's own documented invariant) and `HEAD` was always the
# pre-`.recurve/init` baseline commit -- the governor was structurally
# unreachable on every single A9 cell, not failing on any task's merits.
#
# RED-first: before commit_snapshot_for_governor existed, nothing ever
# committed the agent's real work or the .recurve/claims/ directory that
# _recurve_init creates -- HEAD never contained a valid claims snapshot.
#
# With $TRAP_FIXTURE: an implementation that stages (`git add -A`) but
# never actually commits -- the tree stays dirty, so a snapshot built from
# HEAD afterward still cannot resolve.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }
command -v git >/dev/null || { echo "git unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_commit.py" ] || { echo "trap fixture missing broken_commit.py"; exit 2; }
  T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
  (cd "$T" && git init -q && git config user.email t@t && git config user.name t \
     && echo a > f.txt && git add -A && git commit -q --no-gpg-sign -m init)
  echo b > "$T/f.txt"   # a real, uncommitted change -- what a real agent's fix looks like
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_commit', '$TRAP_FIXTURE/broken_commit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from pathlib import Path
mod.broken_commit_snapshot_for_governor(Path('$T'))
import subprocess
r = subprocess.run(['git', 'status', '--porcelain'], cwd='$T', capture_output=True, text=True)
print('DIRTY' if r.stdout.strip() else 'CLEAN')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    DIRTY)
      echo "ours=broken_commit staged but never committed -- tree still dirty after the call "\
           "oracle=must leave a clean tree so a snapshot at HEAD can resolve -- correctly caught the never-commits bug"
      exit 1 ;;
    CLEAN)
      echo "ours=broken_commit unexpectedly left a clean tree oracle=the fixture failed to exercise the never-commits bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
git init -q "$T"
git -C "$T" config user.email t@t
git -C "$T" config user.name t
echo a > "$T/f.txt"
git -C "$T" add -A
git -C "$T" commit -q --no-gpg-sign -m init

out="$(EVAL="$EVAL" python3 -c "
import sys, subprocess
sys.path.insert(0, '$EVAL')
try:
    from evallib.swebench_pipeline import commit_snapshot_for_governor
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
from pathlib import Path
T = Path('$T')

def log_count():
    r = subprocess.run(['git', 'log', '--oneline'], cwd=T, capture_output=True, text=True)
    return len(r.stdout.strip().splitlines())

def is_clean():
    r = subprocess.run(['git', 'status', '--porcelain'], cwd=T, capture_output=True, text=True)
    return not r.stdout.strip()

# 1. a dirty tree (a real, uncommitted 'agent fix') gets committed.
(T / 'f.txt').write_text('b\n')
(T / '.recurve').mkdir()
(T / '.recurve' / 'marker').write_text('x\n')
before = log_count()
commit_snapshot_for_governor(T)
assert log_count() == before + 1, 'expected exactly one new commit'
assert is_clean(), 'tree must be clean (committable state) after the call'

# 2. HEAD now genuinely contains the .recurve/ state -- a snapshot from
# HEAD would actually find it (the whole point of this claim).
r = subprocess.run(['git', 'show', 'HEAD:.recurve/marker'], cwd=T, capture_output=True, text=True)
assert r.returncode == 0 and r.stdout.strip() == 'x', ('HEAD does not contain the real state', r.stdout, r.stderr)

# 3. calling it again with NOTHING changed (already clean) must not raise
# and must not create a spurious empty commit.
before2 = log_count()
commit_snapshot_for_governor(T)
assert log_count() == before2, 'a clean tree must not produce a new (empty) commit'

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW8 governor-snapshot commit wrong: $(printf '%s' "$out"|tail -1) oracle=a dirty tree is committed exactly once; a clean tree is a no-op; HEAD genuinely contains the current state"; exit 1; }
echo "the harness commits the current working-tree state itself before the governor is consulted -- HEAD always contains the real, current state regardless of whether the agent committed anything"
exit 0
