#!/usr/bin/env bash
# AB-4: shared reviewer plumbing, written once (docs/plans/ablation-infra.md
# AI11). RED-first: until recurvelib.adapters._shared.reviewer_base exists
# the probe is RED.
#
# With $TRAP_FIXTURE: a candidate adapters/ tree with one adapter file that
# reimplements subprocess plumbing directly instead of importing
# reviewer_base. adapters_not_using_shared must flag it (RED).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    pass
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters._shared.reviewer_base import (
        run_claim_reviewer, adapters_not_using_shared,
    )
except ImportError:
    print("ours=no recurvelib.adapters._shared.reviewer_base yet "
          "oracle=isolation+snapshot+provenance wiring written once")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if fixture:
    candidate_root = Path(fixture) / "adapters"
    bad = adapters_not_using_shared(candidate_root)
    names = sorted(p.name for p in bad)
    if not names:
        print("ours=no offending adapter flagged oracle=the candidate reimplements plumbing "
              "directly (fixture's gaming candidate slipped through)")
        sys.exit(0)
    print(f"adapters_not_using_shared correctly flags {names} as reimplementing "
          f"plumbing instead of importing reviewer_base")
    sys.exit(1)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

d = Path(tempfile.mkdtemp(prefix="ab4-repo-"))
subprocess.run(["git", "init", "-q"], cwd=d, check=True)
empty_hooks = Path(tempfile.mkdtemp(prefix="ab4-nohooks-"))
subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
(d / "committed.txt").write_text("hello from the snapshot\n")
subprocess.run(["git", "add", "-A"], cwd=d, check=True)
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                "commit", "-q", "--no-gpg-sign", "-m", "initial"], cwd=d, check=True)

# 1. run_claim_reviewer composes snapshot + isolation + provenance in one call.
inv = run_claim_reviewer(d, "HEAD", "X-1", ["cat", "committed.txt"])
check("reviewer invocation reads the snapshot's committed content",
      inv.returncode == 0 and inv.stdout.strip() == "hello from the snapshot")
check("reviewer invocation pins a real snapshot commit", len(inv.snapshot_commit) == 40)
check("reviewer invocation carries a provenance envelope", hasattr(inv.provenance, "strength"))

# 2. the lint-shaped check: a clean adapters/ tree (one that imports
# reviewer_base) is not flagged.
clean_root = Path(tempfile.mkdtemp(prefix="ab4-clean-"))
(clean_root / "adversary").mkdir(parents=True)
(clean_root / "adversary" / "cross_model.py").write_text(
    "from recurvelib.adapters._shared.reviewer_base import run_claim_reviewer\n"
    "def review(claim):\n    return run_claim_reviewer(*claim)\n"
)
check("a clean adapter importing reviewer_base is not flagged",
      adapters_not_using_shared(clean_root) == [])

# 3. a dirty adapters/ tree (reimplements subprocess directly) IS flagged.
dirty_root = Path(tempfile.mkdtemp(prefix="ab4-dirty-"))
(dirty_root / "adversary").mkdir(parents=True)
(dirty_root / "adversary" / "rogue.py").write_text(
    "import subprocess\n"
    "def review(claim):\n    return subprocess.run(['echo', 'rolled my own'])\n"
)
flagged = adapters_not_using_shared(dirty_root)
check("an adapter reimplementing subprocess plumbing is flagged", len(flagged) == 1
      and flagged[0].name == "rogue.py")

print("isolation-executor invocation, snapshot construction, and provenance attachment "
      "are written once in _shared.reviewer_base; a lint-shaped check flags an adapter "
      "that reimplements them directly")
sys.exit(0)
PYEOF
