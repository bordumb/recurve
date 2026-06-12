#!/usr/bin/env bash
# TK-9: parallel lanes land through one gated serialization point — worktree
# isolation, disjoint suites, first-to-green wins, gate-failing candidates
# reverted and discarded, never merged. RED-first: no parallel loop is RED.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable — cannot measure"; exit 2; }

if [ -n "${TRAP_FIXTURE:-}" ]; then
  # Counterexample: a gateless lander corrupts a guarded tree. The
  # post-landing fleet-gate invariant MUST catch it (probe goes RED).
  python3 - "$ROOT" "$TRAP_FIXTURE" <<'PYEOF'
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = Path(sys.argv[1]), Path(sys.argv[2])
with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    tree = base / "tree"
    tree.mkdir()
    (tree / "feature.txt").write_text("good\n")
    proj = base / "proj"
    s = proj / "claims" / "s"
    (s / "probes").mkdir(parents=True)
    p = s / "probes" / "g.sh"
    p.write_text('#!/usr/bin/env bash\ngrep -q good ../../../tree/feature.txt '
                 '&& exit 0\necho "ours=corrupted oracle=good"; exit 1\n')
    p.chmod(0o755)
    (s / "gaps.yaml").write_text(
        "- id: S-1\n  title: guard\n  class: friction\n  status: closed\n"
        "  severity: cosmetic\n  reads: none\n  smallest_fix: f\n  probe: probes/g.sh\n")
    (proj / "recurve.toml").write_text(
        '[project]\nname = "x"\ndefault_reads = "none"\n[target]\ntree = "../tree"\n'
        '[gate]\ntraps = "off"\n[reads.none]\nmethod = "none"\n[suites.s]\ndir = "claims/s"\n')
    subprocess.run(["bash", str(fixture / "gateless-lander.sh"), str(tree)],
                   capture_output=True)
    r = subprocess.run([sys.executable, str(root / "recurve"), "--config",
                        str(proj / "recurve.toml"), "matrix", "--gate"],
                       capture_output=True, text=True)
if r.returncode != 0:
    print("ours=gateless landing corrupted a guard oracle=every landing gate-checked")
    sys.exit(1)
print("post-landing fleet gate failed to notice the corruption")
sys.exit(0)
PYEOF
  exit $?
fi

TEMPLATE="$ROOT/templates/workflows/burndown-parallel.sh"
if [ ! -f "$TEMPLATE" ]; then
  echo "ours=no parallel loop oracle=worktree lanes + gated serialization (plan §15.9)"
  exit 1
fi
python3 - "$ROOT" "$TEMPLATE" <<'PYEOF'
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root, template = Path(sys.argv[1]), Path(sys.argv[2])
GIT = ["git", "-c", "user.name=probe", "-c", "user.email=probe@invalid",
       "-c", "commit.gpgsign=false"]

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    tree = base / "tree"
    tree.mkdir()
    (tree / "README").write_text("scenario tree\n")
    subprocess.run(["git", "-C", str(tree), "init", "-q"], check=True, capture_output=True)
    subprocess.run(GIT[:1] + ["-C", str(tree)] + GIT[1:] + ["add", "-A"], check=True, capture_output=True)
    subprocess.run(GIT[:1] + ["-C", str(tree)] + GIT[1:] + ["commit", "-qm", "base"], check=True, capture_output=True)

    proj = base / "proj"
    for s, gid in (("s1", "S1-1"), ("s2", "S2-1"), ("s3", "S3-1")):
        d = proj / "claims" / s
        (d / "probes").mkdir(parents=True)
        p = d / "probes" / "p.sh"
        p.write_text(f'#!/usr/bin/env bash\n[ -f ../../../tree/feature-{gid}.txt ] '
                     f'&& {{ echo present; exit 0; }}\n'
                     f'echo "ours=missing oracle=feature-{gid}.txt"; exit 1\n')
        p.chmod(0o755)
        (d / "gaps.yaml").write_text(
            f"- id: {gid}\n  title: feature {gid}\n  class: missing-surface\n"
            f"  status: open\n  severity: feature\n  reads: none\n"
            f"  smallest_fix: create it\n  probe: probes/p.sh\n")
    (proj / "recurve.toml").write_text(
        '[project]\nname = "scenario"\ndefault_reads = "none"\n[target]\ntree = "../tree"\n'
        '[gate]\ntraps = "off"\n[reads.none]\nmethod = "none"\n'
        '[suites.s1]\ndir = "claims/s1"\n[suites.s2]\ndir = "claims/s2"\n'
        '[suites.s3]\ndir = "claims/s3"\n')

    # Lane agent: closes its gap honestly — except in s3, which produces a
    # useless candidate (wrong file) that must be discarded at the gate.
    agent = base / "agent.sh"
    agent.write_text(
        '#!/usr/bin/env bash\ncat > /dev/null\n'
        'if [ "$LANE_GAP" = "S3-1" ]; then touch "$LANE_TREE/feature-WRONG.txt"\n'
        'else touch "$LANE_TREE/feature-$LANE_GAP.txt"; fi\n'
        'printf \'{"schema_version":"1.0.0","project":"scenario","cycle":"%s",'
        '"gap":"%s","status":"closed","attempts":1,"wall_clock_s":1.0,'
        '"net_new_gaps":0,"verdicts_before":{"green":0,"red":1},'
        '"verdicts_after":{"green":1,"red":0}}\' "$LANE_GAP" "$LANE_GAP" '
        '> "$RECURVE_RESULT_FILE"\n')
    agent.chmod(0o755)

    loop = base / "loop.sh"
    loop.write_text(template.read_text().replace("{{PROG}}", "recurve")
                    .replace("{{TREE}}", "../tree").replace("{{PARALLEL}}", "2")
                    .replace("{{CAP}}", "4").replace("{{COMMIT_POLICY}}", "unsigned-per-cycle"))
    loop.chmod(0o755)

    env = {**os.environ,
           "RECURVE_BIN": f"{sys.executable} {root / 'recurve'}",
           "AGENT_CMD": f"bash {agent}", "PARALLEL": "2", "CAP": "4",
           "TREE_DIR": str(tree)}
    r = subprocess.run(["bash", str(loop)], cwd=proj, capture_output=True,
                       text=True, env=env, timeout=300)
    out = r.stdout + r.stderr

    def fail(msg):
        print(f"ours={msg} oracle=gated serialization (never merge two sculpts)")
        print(out[-400:])
        sys.exit(1)

    if not (tree / "feature-S1-1.txt").exists() or not (tree / "feature-S2-1.txt").exists():
        fail("honest lanes did not land")
    if (tree / "feature-WRONG.txt").exists():
        fail("a gate-failing candidate stayed on the tree (must be reverted)")
    log = subprocess.run(["git", "-C", str(tree), "log", "--oneline"],
                         capture_output=True, text=True).stdout.splitlines()
    landings = [l for l in log if "landed" in l]
    if len(landings) < 2:
        fail(f"expected 2 separate gate-checked landing commits, saw {len(landings)}")
    if "discard" not in out:
        fail("the discarded lane was not reported")
    ledgers = "".join((proj / "claims" / s / "gaps.yaml").read_text()
                      for s in ("s1", "s2"))
    if ledgers.count("status: closed") != 2:
        fail("winners were not promoted after their gated landing")
    if "status: closed" in (proj / "claims" / "s3" / "gaps.yaml").read_text():
        fail("the discarded lane's gap must stay open")
    g = subprocess.run([sys.executable, str(root / "recurve"), "--config",
                        str(proj / "recurve.toml"), "matrix", "--gate"],
                       capture_output=True, text=True)
    if g.returncode != 0:
        fail("fleet gate not green after the run")

print("two lanes landed sequentially under the gate; the bad candidate was reverted and discarded")
sys.exit(0)
PYEOF
