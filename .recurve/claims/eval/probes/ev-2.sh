#!/usr/bin/env bash
# EV-2: the Materializer turns a task into a fresh workspace and enforces the
# oracle quarantine — the hidden `test` field never enters the workspace. arms.py
# maps an arm name to its spec (A0 = bare task + empty solution.py; A3 = the same
# workspace, recurve-init'd). materialize.py builds the git-init'd tmpdir and
# refuses (assert_quarantined raises) any workspace that contains the hidden test.
#
# RED until the modules exist. The trap plants the hidden test text into a
# workspace and proves assert_quarantined refuses it.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/../../../.." && pwd)"
EVAL="$REPO/eval"
command -v python3 >/dev/null || { echo "python3 unavailable"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  [ -f "$TRAP_FIXTURE/claims" ] || { echo "trap fixture missing claims file"; exit 2; }
  python3 - "$EVAL" <<'PY'
import sys, tempfile, pathlib
sys.path.insert(0, sys.argv[1])
try:
    from evallib.materialize import assert_quarantined, QuarantineError
except Exception as e:
    print("materialize incomplete:", e); sys.exit(2)
task = {"task_id": "t/1", "instruct_prompt": "write add(a,b)",
        "test": "import unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)"}
d = pathlib.Path(tempfile.mkdtemp())
(d / "solution.py").write_text("")
(d / "LEAK.txt").write_text(task["test"])   # the hidden oracle leaked into the workspace
try:
    assert_quarantined(d, task)
except QuarantineError:
    print("assert_quarantined refused the leaked workspace"); sys.exit(1)   # guard holds → RED
print("assert_quarantined ACCEPTED a leaked workspace"); sys.exit(0)        # guard broken → trap fails
PY
  rc=$?
  case "$rc" in
    1) echo "materializer refuses a workspace containing the hidden test"; exit 1 ;;
    0) echo "materializer accepted a leaked workspace (fixture claimed it does)"; exit 0 ;;
    *) echo "materialize incomplete — cannot measure"; exit 2 ;;
  esac
fi

python3 - "$EVAL" "$REPO/recurve" <<'PY'
import sys, tempfile, pathlib, subprocess
sys.path.insert(0, sys.argv[1]); RECURVE = sys.argv[2]
try:
    from evallib.arms import arm_spec
    from evallib.materialize import materialize, assert_quarantined, QuarantineError
except Exception as e:
    print("ours=evallib.materialize/arms missing:", e, "oracle=materialize + arm_spec"); sys.exit(1)
task = {"task_id": "t/add", "instruct_prompt": "write add(a,b) that returns the sum",
        "test": "import unittest\nclass T(unittest.TestCase):\n def test(self): self.assertEqual(add(1,2),3)"}

# arm specs: A0 bare, A3 recurve-init'd
a0, a3 = arm_spec("A0"), arm_spec("A3")
assert a0.recurve is False and a3.recurve is True, f"arm specs wrong: {a0} {a3}"

# A0 workspace: task present, empty solution, hidden test NOT present, no .recurve
d0 = pathlib.Path(tempfile.mkdtemp()) / "ws"
materialize(task, "A0", d0, recurve_cmd=RECURVE)
files = list(d0.rglob("*"))
assert (d0 / "solution.py").exists(), "no solution.py"
assert any(task["instruct_prompt"] in p.read_text() for p in d0.rglob("*") if p.is_file()), "prompt missing"
assert not (d0 / ".recurve").exists(), "A0 should not be recurve-init'd"
blob = "".join(p.read_text(errors="ignore") for p in d0.rglob("*") if p.is_file())
assert task["test"] not in blob, "HIDDEN TEST LEAKED into A0 workspace"
assert (d0 / ".git").exists(), "workspace not git-init'd"

# A3 workspace: recurve-init'd, hidden test still absent, quarantine passes
d3 = pathlib.Path(tempfile.mkdtemp()) / "ws"
materialize(task, "A3", d3, recurve_cmd=RECURVE)
assert (d3 / ".recurve").exists() or (d3 / "recurve.toml").exists(), "A3 not recurve-init'd"
blob3 = "".join(p.read_text(errors="ignore") for p in d3.rglob("*") if p.is_file())
assert task["test"] not in blob3, "HIDDEN TEST LEAKED into A3 workspace"
assert_quarantined(d3, task)  # must not raise on a clean workspace
print("OK")
PY
[ $? -eq 0 ] || { echo "ours=materializer wrong (leak/arm/scaffold) oracle=A0 bare + A3 init'd, hidden test quarantined"; exit 1; }
echo "materializer builds A0/A3 workspaces and quarantines the hidden test"
exit 0
