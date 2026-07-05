#!/usr/bin/env bash
# SW-2: the agent's workspace is real and working, but structurally
# oracle-free — the container is built from the environment image WITHOUT
# test_patch, and `assert_quarantined_swe` is the load-bearing guard that
# refuses a workspace before an agent ever sees it if the hidden test's
# content leaked in anyway.
#
# RED-first: before evallib/swebench_workspace.py existed, there was no
# WorkspacePort["swe_bench_repo"] at all and no per-line quarantine check for
# a diff-shaped oracle (materialize.assert_quarantined only understands a
# single hidden `test` string, BigCodeBench's shape).
#
# With $TRAP_FIXTURE: a quarantine check that requires the WHOLE raw patch
# text (headers included) as one substring — real leaked content is always a
# SUBSET of the patch (just the `+` lines), so this check almost never fires.
# The real requirement must catch a leak of just the meaningful content.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

FIXTURES='
TEST_PATCH = """diff --git a/tests/test_blueprints.py b/tests/test_blueprints.py
--- a/tests/test_blueprints.py
+++ b/tests/test_blueprints.py
@@ -256,6 +256,11 @@ def test_dotted_name_not_allowed(app, client):
         flask.Blueprint(\"app.ui\", __name__)


+def test_empty_name_not_allowed(app, client):
+    with pytest.raises(ValueError):
+        flask.Blueprint(\"\", __name__)
+
+
 def test_dotted_names_from_app(app, client):
     test = flask.Blueprint(\"test\", __name__)
"""

# A REAL leak: the container tree contains just the added test function
# (the diff headers themselves never appear in a real source file).
LEAKED_TREE = {
    "/testbed/tests/test_blueprints.py":
        "def test_empty_name_not_allowed(app, client):\n"
        "    with pytest.raises(ValueError):\n"
        "        flask.Blueprint(\"\", __name__)\n",
}
CLEAN_TREE = {"/testbed/src/flask/blueprints.py": "def __init__(self, name):\n    pass\n"}
'

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/broken_assert_quarantined.py" ] || { echo "trap fixture missing broken_assert_quarantined.py"; exit 2; }
  out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
import importlib.util
spec = importlib.util.spec_from_file_location('broken_assert_quarantined', '$TRAP_FIXTURE/broken_assert_quarantined.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    mod.assert_quarantined_swe(LEAKED_TREE, TEST_PATCH)
    print('ACCEPTED_LEAK')
except mod.QuarantineError:
    print('REJECTED_LEAK')
" 2>&1)" || { echo "trap harness could not run: $out"; exit 2; }
  case "$out" in
    ACCEPTED_LEAK)
      echo "ours=whole-patch-substring check missed a real per-line leak "\
           "oracle=must raise QuarantineError — correctly caught the substring-only bug"
      exit 1 ;;
    REJECTED_LEAK)
      echo "ours=broken_assert_quarantined unexpectedly caught the leak "\
           "oracle=the fixture failed to exercise the substring-only bug"
      exit 0 ;;
    *) echo "trap scenario produced unexpected output: $out"; exit 2 ;;
  esac
fi

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

out="$(EVAL="$EVAL" python3 -c "
import sys; sys.path.insert(0, '$EVAL')
$FIXTURES
try:
    from evallib.swebench_workspace import (
        test_patch_signals, assert_quarantined_swe, materialize_swe_repo_workspace,
        WORKSPACE_PORT_NAME,
    )
    from evallib.materialize import QuarantineError, WORKSPACE_PORTS
except Exception as e:
    print('MISSING', e); raise SystemExit(0)

# 1. registered in the shared WorkspacePort registry — one line, kernel untouched.
assert WORKSPACE_PORT_NAME in WORKSPACE_PORTS, WORKSPACE_PORTS.keys()

# 2. signal extraction pulls the meaningful + lines, skips diff plumbing.
sig = test_patch_signals(TEST_PATCH)
assert any('test_empty_name_not_allowed' in s for s in sig), sig
assert not any(s.startswith('+++') or s.startswith('@@') for s in sig), sig

# 3. a clean tree passes.
assert_quarantined_swe(CLEAN_TREE, TEST_PATCH)

# 4. a real (per-line, reformatted) leak is caught.
try:
    assert_quarantined_swe(LEAKED_TREE, TEST_PATCH)
    raise AssertionError('leak was NOT caught')
except QuarantineError:
    pass

# 5. end to end: materialize_swe_repo_workspace refuses BEFORE writing
# anything agent-visible, when the container's real tree leaks.
import tempfile, pathlib
task = {'instance_id': 't/1', 'repo': 'x/y', 'problem_statement': 'p', 'test_patch': TEST_PATCH}
dest = pathlib.Path(tempfile.mkdtemp()) / 'ws'

def bad_factory(digest):
    return {'container_id': 'c1', 'workdir': '/testbed'}
def bad_lister(cid, wd):
    return LEAKED_TREE
def bad_extract(cid, wd, d):
    raise AssertionError('extract_tree must never run after a quarantine failure')

try:
    materialize_swe_repo_workspace(dest, task, environment_image_digest='sha256:x',
                                   container_factory=bad_factory, file_lister=bad_lister,
                                   extract_tree=bad_extract)
    raise AssertionError('materialize did not refuse a leaking workspace')
except QuarantineError:
    pass
assert not dest.exists() or not any(dest.iterdir()), 'a refused workspace must stay empty — nothing agent-visible'

# 6. a clean container materializes fully (TASK.md, testbed/, run_tests.sh, container.json).
def good_lister(cid, wd):
    return CLEAN_TREE
def good_extract(cid, wd, d):
    d.mkdir(parents=True, exist_ok=True)
    (d / 'blueprints.py').write_text('def __init__(self, name):\n    pass\n')
    import subprocess
    subprocess.run(['git', 'init', '-q'], cwd=d, check=True)

dest2 = pathlib.Path(tempfile.mkdtemp()) / 'ws'
materialize_swe_repo_workspace(dest2, task, environment_image_digest='sha256:x',
                               container_factory=bad_factory, file_lister=good_lister,
                               extract_tree=good_extract, recurve_cmd='true')
assert (dest2 / 'TASK.md').exists()
assert (dest2 / 'testbed').is_dir()
assert (dest2 / 'run_tests.sh').exists()
assert (dest2 / 'container.json').exists()

print('OK')
" 2>&1)"
printf '%s\n' "$out" | grep -q '^OK$' || { echo "ours=SW2 workspace/quarantine wrong: $(printf '%s' "$out"|tail -1) oracle=a real, working workspace that structurally never contains test_patch content"; exit 1; }
echo "WorkspacePort['swe_bench_repo'] registered; a real container tree leaking test_patch content is refused before the agent ever sees it; a clean container materializes TASK.md/testbed/run_tests.sh/container.json"
exit 0
