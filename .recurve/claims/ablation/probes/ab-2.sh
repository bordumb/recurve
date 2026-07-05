#!/usr/bin/env bash
# AB-2: context snapshots enforce the exclusion boundary mechanically
# (docs/plans/ablation-infra.md AI3). RED-first: until
# recurvelib.adapters.snapshot exists the probe is RED.
#
# With $TRAP_FIXTURE: a broken_snapshot.py alternate of build_claim_snapshot
# — either ignoring a dirty tree, or failing to strip existing traps when
# asked to. The probe runs the SAME assertions against the broken function
# and must find it wrong (RED = still discriminating).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    import subprocess as _sp  # noqa: F401 — selfcheck only
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.snapshot import build_claim_snapshot, SnapshotError
except ImportError:
    print("ours=no recurvelib.adapters.snapshot yet oracle=ClaimSnapshot via git archive")
    sys.exit(1)  # RED-first


def toy_repo():
    d = Path(tempfile.mkdtemp(prefix="ab2-repo-"))
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    # This machine sets a GLOBAL core.hooksPath (an auths post-commit hook
    # that writes .auths/roots, leaving a fresh repo "dirty" right after its
    # first commit) — override it locally so a throwaway test repo's
    # cleanliness reflects only what THIS test committed.
    empty_hooks = Path(tempfile.mkdtemp(prefix="ab2-nohooks-"))
    subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    (d / "committed.txt").write_text("committed content\n")
    (d / "probes").mkdir()
    (d / "probes" / "g.trap").mkdir()
    (d / "probes" / "g.trap" / "ce").mkdir()
    (d / "probes" / "g.trap" / "ce" / "marker").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-gpg-sign", "-m", "initial"], cwd=d, check=True)
    return d


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if fixture:
    broken_path = Path(fixture) / "broken_snapshot.py"
    spec = importlib.util.spec_from_file_location("bsnap", broken_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    broken_build = mod.build_claim_snapshot

    scenario = (Path(fixture) / "scenario").read_text().strip()
    repo = toy_repo()

    if scenario == "dirty_tree_not_refused":
        (repo / "committed.txt").write_text("MUTATED UNCOMMITTED\n")
        try:
            snap = broken_build(repo, "HEAD", "X-1", require_clean=True)
        except Exception:
            print("ours=broken build refused too oracle=expected it to silently accept "
                  "(this fixture did not exercise the intended bug)")
            sys.exit(0)
        print(f"ours=dirty tree silently accepted (root={snap.root}) "
              f"oracle=must refuse a dirty tree — correctly caught the bug")
        sys.exit(1)

    if scenario == "traps_leaked_when_excluded":
        snap = broken_build(repo, "HEAD", "X-1", include_existing_traps=False,
                            trap_relpaths=("probes/g.trap",))
        if (Path(snap.root) / "probes" / "g.trap").exists():
            print("ours=trap dir present despite include_existing_traps=False "
                  "oracle=must be stripped — correctly caught the leak")
            sys.exit(1)
        print("ours=trap dir absent oracle=expected it to leak "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

repo = toy_repo()

# 1. a clean tree builds a snapshot whose root has exactly the committed content.
snap = build_claim_snapshot(repo, "HEAD", "X-1", include_existing_traps=True)
check("committed file present in the snapshot", (Path(snap.root) / "committed.txt").read_text() == "committed content\n")
check("snapshot pins a real commit sha", len(snap.commit) == 40)

# 2. a dirty tree is refused when require_clean=True (the default).
(repo / "committed.txt").write_text("DIRTY UNCOMMITTED CHANGE\n")
try:
    build_claim_snapshot(repo, "HEAD", "X-2")
    check("dirty tree refused", False)
except SnapshotError:
    pass

# 3. even with require_clean=False, the archive never contains the dirty
# change — git archive only ever contains committed content (defense in depth).
snap3 = build_claim_snapshot(repo, "HEAD", "X-3", require_clean=False, include_existing_traps=True)
check("dirty change never leaks into the archive regardless of require_clean",
      (Path(snap3.root) / "committed.txt").read_text() == "committed content\n")

# 4. include_existing_traps=False strips the named trap paths.
snap4 = build_claim_snapshot(repo, "HEAD", "X-4", require_clean=False,
                             include_existing_traps=False, trap_relpaths=("probes/g.trap",))
check("existing traps stripped when withheld", not (Path(snap4.root) / "probes" / "g.trap").exists())

# 5. include_existing_traps=True (the governor's mechanical tier) keeps them.
snap5 = build_claim_snapshot(repo, "HEAD", "X-5", require_clean=False, include_existing_traps=True)
check("existing traps kept when included", (Path(snap5.root) / "probes" / "g.trap" / "ce" / "marker").exists())

# 6. an unresolvable ref refuses rather than silently comparing against self.
try:
    build_claim_snapshot(repo, "not-a-real-ref-at-all", "X-6", require_clean=False)
    check("bad ref refused", False)
except SnapshotError:
    pass

print("ClaimSnapshot is built only from git archive of a pinned commit — a dirty tree is "
      "refused by default, and never leaks into the archive even when permitted; the "
      "include_existing_traps knob controls exactly what §5 says it should")
sys.exit(0)
PYEOF
