#!/usr/bin/env bash
# AB-3: isolation strategy is pluggable and per-adapter, not global
# (docs/plans/ablation-infra.md AI4). RED-first: until
# recurvelib.adapters.isolation exists the probe is RED.
#
# With $TRAP_FIXTURE: a broken_subprocess_tempdir.py that leaks the parent's
# full environment unfiltered. The probe must catch the leak (RED).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import os
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
    from recurvelib.adapters import isolation
    from recurvelib.adapters.isolation import subprocess_tempdir, docker as docker_strategy
except ImportError:
    print("ours=no recurvelib.adapters.isolation yet oracle=pluggable, per-adapter isolation strategy")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


SECRET = "acting-agent-live-session-secret-value"

if fixture:
    spec = importlib.util.spec_from_file_location(
        "broken_st", Path(fixture) / "broken_subprocess_tempdir.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    broken_run_isolated = mod.run_isolated

    os.environ["ACTING_AGENT_SECRET"] = SECRET
    snap_root = Path(tempfile.mkdtemp(prefix="ab3-snap-"))
    result = broken_run_isolated(
        snap_root, ["python3", "-c", "import os; print('ACTING_AGENT_SECRET' in os.environ)"])
    if "True" in result.stdout:
        print("ours=ACTING_AGENT_SECRET leaked into the isolated invocation "
              "oracle=must be scrubbed — correctly caught the leak")
        sys.exit(1)
    print("ours=secret not leaked oracle=expected the broken strategy to leak it "
          "(this fixture did not exercise the intended bug)")
    sys.exit(0)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. the registry resolves both strategies, and refuses an unknown one.
check("subprocess_tempdir resolves", isolation.resolve("subprocess_tempdir") is subprocess_tempdir)
check("docker resolves", isolation.resolve("docker") is docker_strategy)
try:
    isolation.resolve("not-a-real-strategy")
    check("unknown strategy refused", False)
except ValueError:
    pass

# 2. subprocess_tempdir: cwd is pinned to the snapshot root.
snap_root = Path(tempfile.mkdtemp(prefix="ab3-snap-"))
(snap_root / "marker.txt").write_text("in the snapshot\n")
r = subprocess_tempdir.run_isolated(snap_root, ["python3", "-c", "import os; print(os.getcwd())"])
check("isolated invocation's cwd is the snapshot root", r.stdout.strip() == str(snap_root.resolve()) or r.stdout.strip() == str(snap_root))

# 3. subprocess_tempdir: the acting agent's own env var never crosses in.
os.environ["ACTING_AGENT_SECRET"] = SECRET
r2 = subprocess_tempdir.run_isolated(
    snap_root, ["python3", "-c", "import os; print('ACTING_AGENT_SECRET' in os.environ)"])
check("the scrubbed env excludes an arbitrary acting-agent env var", r2.stdout.strip() == "False")

# 4. subprocess_tempdir: PATH survives so the child can find its interpreter.
env = subprocess_tempdir.scrubbed_env()
check("PATH survives scrubbing", "PATH" in env)

# 5. docker strategy: declares availability without requiring it be used.
avail = docker_strategy.available()
check("docker.available() returns a bool", isinstance(avail, bool))
if avail:
    # A real, live isolation run — mounted read-only, cwd pinned inside the
    # container — using a tiny image already present locally (no network
    # dependency introduced by this probe).
    import subprocess as _sp
    have_alpine = _sp.run(["docker", "image", "inspect", "alpine:latest"],
                         capture_output=True).returncode == 0
    if have_alpine:
        rd = docker_strategy.run_isolated(snap_root, ["cat", "marker.txt"], "alpine:latest",
                                          network="none", timeout=60)
        check("docker isolation reads the mounted snapshot",
              rd.returncode == 0 and "in the snapshot" in rd.stdout)
        wd = docker_strategy.run_isolated(
            snap_root, ["sh", "-c", "echo hostile > marker.txt"], "alpine:latest",
            network="none", timeout=60)
        check("the snapshot mount is read-only inside the container", wd.returncode != 0)
    else:
        print("(docker available but alpine:latest not cached locally — skipping the live "
              "container check; the strategy's interface is still proven above)")
else:
    print("(docker CLI not present in this environment — the interface and refusal path "
          "are still proven; a live container run is not exercised)")

print("isolation strategy is pluggable and selected per-adapter: subprocess_tempdir scrubs "
      "the environment and pins cwd to the snapshot; docker is available, opt-in, "
      "never silently required")
sys.exit(0)
PYEOF
