#!/usr/bin/env bash
# SW-9: the governor reviewer reads REAL content (closed claims' own
# title/smallest_fix/observed, their probe script's actual text, and any
# evidence files' current content) instead of a git diff -- the isolated
# snapshot it runs in (`recurvelib.adapters.snapshot._archive`: `git
# archive` + `tar -x`) has NO `.git` directory at all, by design (the same
# isolation every reviewer gets), so a git-diff-based review can only ever
# see an empty diff and silently, vacuously clear everything -- a false
# "STOP-SUCCESS" that never actually reviewed anything, discovered running
# the REAL smoke (SW6). Truncation is marked explicitly, never silent: a
# probe script one line over an earlier, tighter cap was shown to a
# reviewer as "incomplete", when the real file was whole -- the review's
# own excerpting was the actual defect, and an unmarked cut is
# indistinguishable from a genuinely broken file.
#
# RED-first: before this claim's implementation, `_diff()` used `git diff
# HEAD~1 HEAD` (or `git show HEAD`) inside the archived snapshot -- always
# empty there, always a silent, uninformed clear.
#
# With $TRAP_FIXTURE: a cap function that truncates SILENTLY (no marker) --
# indistinguishable, to anything reading it, from the file being genuinely
# incomplete.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_cap.py" ] || { echo "trap fixture missing broken_cap.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
import importlib.util
spec = importlib.util.spec_from_file_location('broken_cap', '$TRAP_FIXTURE/broken_cap.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
long_text = 'A' * 50 + 'B' * 50   # 100 chars, cap at 60
out = mod.broken_cap(long_text, 60)
print('MARKED' if 'TRUNCAT' in out else 'UNMARKED')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    UNMARKED)
      echo "ours=broken_cap truncated with no marker -- indistinguishable from a genuinely "\
           "incomplete file oracle=truncation must always be marked -- correctly caught the silent-cut bug"
      exit 1 ;;
    MARKED)
      echo "ours=broken_cap unexpectedly marked its truncation oracle=the fixture failed to exercise the silent-cut bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys, tempfile, json
sys.path.insert(0, '$EVAL')
try:
    from evallib.swebench_governor_reviewer import (
        _cap, _closed_claims, _review_context, main,
    )
except Exception as e:
    print('MISSING', e); raise SystemExit(0)
from pathlib import Path

# 1. _cap: within bounds -> unchanged; over bounds -> marked, never silent.
assert _cap('short', 100) == 'short'
capped = _cap('X' * 100, 60)
assert len(capped) > 60 and 'TRUNCATED' in capped and capped.startswith('X' * 60), capped

# 2. a real, on-disk claims tree: _closed_claims discovers a closed claim
# with its full fields (this is what SW6's own real workspaces look like).
root = Path(tempfile.mkdtemp())
suite = root / '.recurve' / 'claims' / 'core'
(suite / 'probes').mkdir(parents=True)
(suite / 'gaps.yaml').write_text('''
- id: X-1
  title: a real fix
  status: closed
  smallest_fix: did the real thing
  observed: GREEN at 2026-07-06
  probe: probes/x-1.sh
  evidence: [\"src/thing.py:1\"]
''')
(suite / 'probes' / 'x-1.sh').write_text('#!/usr/bin/env bash\necho real probe content\nexit 0\n')
(root / 'src').mkdir()
(root / 'src' / 'thing.py').write_text('def thing():\n    return 1\n')

claims = _closed_claims(root)
assert len(claims) == 1 and claims[0]['id'] == 'X-1', claims

# 3. the review context genuinely contains the claim's real substance --
# not a placeholder, not empty, not a diff.
ctx = _review_context(root, claims)
assert 'a real fix' in ctx and 'echo real probe content' in ctx and 'def thing' in ctx, ctx
assert 'diff --git' not in ctx, 'must never fall back to a (structurally impossible) git diff'

# 4. zero closed claims -> fails closed WITHOUT ever calling the model.
empty_root = Path(tempfile.mkdtemp())
calls = []
def must_not_be_called(model, prompt):
    calls.append(1)
    return '{\"veto\": false}'
import io, contextlib
buf = io.StringIO()
old_argv = sys.argv
sys.argv = ['x', 'some-model']
old_cwd = Path.cwd()
import os
os.chdir(empty_root)
try:
    with contextlib.redirect_stdout(buf):
        main(call_model=must_not_be_called)
finally:
    os.chdir(old_cwd)
    sys.argv = old_argv
assert not calls, 'the model must never be called when there is nothing real to review'
result = json.loads(buf.getvalue().strip())
assert result['vetoes'], ('zero claims must fail closed (veto), not silently clear', result)

# 5. claims present -> the model IS called, with the real substance in the
# prompt, and its verdict is correctly parsed (both clear and veto).
seen_prompts = []
def fake_clear(model, prompt):
    seen_prompts.append(prompt)
    return '{\"veto\": false}'
buf2 = io.StringIO()
os.chdir(root)
try:
    with contextlib.redirect_stdout(buf2):
        main(call_model=fake_clear)
finally:
    os.chdir(old_cwd)
assert seen_prompts and 'a real fix' in seen_prompts[0], seen_prompts
result2 = json.loads(buf2.getvalue().strip())
assert result2['vetoes'] == {}, result2

def fake_veto(model, prompt):
    return '{\"veto\": true, \"reason\": \"fabricated\"}'
buf3 = io.StringIO()
os.chdir(root)
try:
    with contextlib.redirect_stdout(buf3):
        main(call_model=fake_veto)
finally:
    os.chdir(old_cwd)
result3 = json.loads(buf3.getvalue().strip())
assert result3['vetoes'], result3

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW9 governor reviewer content wrong: $(printf '%s' "$out"|tail -1) oracle=the reviewer reads real claim/probe/evidence content, fails closed on zero claims, and never truncates silently"; exit 1; }
echo "the governor reviewer reads real, current claim/probe/evidence content (never a structurally-impossible git diff), fails closed when there is nothing to review, and marks truncation explicitly, never silently"
exit 0
