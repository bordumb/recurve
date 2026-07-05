#!/usr/bin/env bash
# DC-4: the O6-incident regression fixture, at RUN level (R5's acceptance
# criterion). Replays the same incident as DC-3, as a full cycle: every
# claim's own gate green, sharing one correlated-authorship defect. Uses the
# REAL mechanical + mechanical_review governor adapters (AB-7) and the REAL
# capture() rule — not stubs.
#
# RED-first: until recurvelib.adapters.governor.mechanical_review exists (or
# either tier's coverage disagrees with R5's design) the probe is RED.
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
command -v git >/dev/null || { echo "git unavailable"; exit 2; }
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

try:
    from recurvelib.loop.runtime import capture
    from recurvelib.adapters.snapshot import build_cycle_snapshot
    from recurvelib.adapters._shared.provenance import metadata_verified
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.governor.mechanical import MechanicalGovernor
    from recurvelib.adapters.governor.mechanical_review import MechanicalReviewGovernor
except ImportError:
    print("ours=no recurvelib.adapters.governor.mechanical_review yet "
          "oracle=the O6 run-level replay: mechanical misses it, review catches it")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


# --- the same O6 shape as DC-3 (BigCodeBench/13's attempted-vs-succeeded
# misreading), wired as a real recurve claim so the governor can load it. ---

WRONG_SOLUTION = (
    "def task_func(items, should_fail):\n"
    "    attempted = []\n"
    "    for it in items:\n"
    "        if it in should_fail:\n"
    "            continue\n"
    "        attempted.append(it)\n"
    "    return attempted\n"
)
CORRECT_SOLUTION = (
    "def task_func(items, should_fail):\n"
    "    return list(items)\n"
)
# The claim's probe: happy path only — the same-model blind spot, now
# authored to recurve's real probe exit-code contract (0 GREEN / 1 RED).
# recurve's ShellProbeRunner already sets cwd=suite_dir (claims/s) for every
# invocation, so this reads solution.py as a sibling with no path gymnastics.
# Honors TRAP_FIXTURE (a trivial, ORTHOGONAL counterexample unrelated to the
# O6 bug — required by the trap discipline; this claim's whole point is that
# its own trap coverage never reaches the failure case).
CLAIM_PROBE = (
    "#!/usr/bin/env bash\n"
    "if [ -n \"${TRAP_FIXTURE:-}\" ]; then echo unrelated-counterexample; exit 1; fi\n"
    "python3 -c \"import sys; sys.path.insert(0, '.'); from solution import task_func; "
    "r = task_func(['a','b','c'], should_fail=[]); sys.exit(0 if r == ['a','b','c'] else 1)\"\n"
)
REVIEW_REVEALS_THE_BUG = (
    "import json, sys\n"
    "sys.path.insert(0, 'claims/s')\n"
    "from solution import task_func\n"
    "result = task_func(['a', 'b', 'c'], should_fail=['b'])\n"
    "vetoes = {}\n"
    "if result != ['a', 'b', 'c']:\n"
    "    reason = ('task_func drops a failing item instead of including it as attempted; '\n"
    "              'the spec requires every ATTEMPTED item, success or failure -- same '\n"
    "              'misreading as the O6 FTP-downloader incident')\n"
    "    vetoes['O6-1'] = reason\n"
    "print(json.dumps({'served_model': 'adversary-model-x', 'vetoes': vetoes}))\n"
)


def toy_cycle_project(solution_body: str):
    d = Path(tempfile.mkdtemp(prefix="dc4-repo-"))
    (d / "claims" / "s" / "probes").mkdir(parents=True)
    (d / "recurve.toml").write_text(
        "[project]\nname = \"fixture\"\nlabel = \"suite\"\ndefault_reads = \"none\"\n"
        "cycles_dir = \"cycles\"\nschema = \"1\"\n\n[target]\ntree = \".\"\n\n"
        "[gate]\ntraps = \"required\"\nquality = \"pre-launch\"\n\n"
        "[reads.none]\nmethod = \"none\"\n\n[suites.s]\ndir = \"claims/s\"\n"
    )
    (d / "claims" / "s" / "solution.py").write_text(solution_body)
    probe = d / "claims" / "s" / "probes" / "o6-1.sh"
    probe.write_text(CLAIM_PROBE)
    probe.chmod(0o755)
    # A trivial, unrelated trap — required by the trap discipline, orthogonal
    # to the O6 bug (this claim's whole point is that its OWN trap doesn't
    # cover the failure case; that's what makes it a same-model blind spot).
    trap_dir = d / "claims" / "s" / "probes" / "o6-1.trap" / "ce"
    trap_dir.mkdir(parents=True)
    (trap_dir / "marker").write_text("x\n")
    (d / "claims" / "s" / "gaps.yaml").write_text(
        "- id: O6-1\n  title: O6-shaped claim\n  class: missing-surface\n  status: closed\n"
        "  severity: feature\n  reads: none\n  evidence: [\"x:1\"]\n"
        "  observed: GREEN by construction\n  smallest_fix: none\n  probe: probes/o6-1.sh\n"
    )
    (d / "claims" / "s" / "GAPS.md").write_text("## O6-1\n")
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    empty_hooks = Path(tempfile.mkdtemp(prefix="dc4-nohooks-"))
    subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-gpg-sign", "-m", "i"], cwd=d, check=True)
    return d


if fixture:
    import importlib.util

    scenario = (Path(fixture) / "scenario").read_text().strip()
    if scenario == "mechanical_overreaches_into_content_review":
        # A misconception this trap guards against: a mechanical governor
        # that ALSO does content-level review would conflate the two tiers
        # R5 deliberately keeps separate (near-free/no-LLM vs. a real model
        # pass). A broken variant that over-reaches this way would WRONGLY
        # veto the O6 replay via the mechanical tier alone.
        spec = importlib.util.spec_from_file_location(
            "bmoverreach", Path(fixture) / "broken_mechanical_overreaching.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        d = toy_cycle_project(WRONG_SOLUTION)
        cycle = build_cycle_snapshot(d, "HEAD", ["O6-1"], include_existing_traps=True)
        v = mod.OverreachingMechanicalGovernor().audit(cycle)
        if not v.is_clear:
            print("ours=the over-reaching mechanical variant vetoed the O6 replay "
                  "oracle=the real mechanical tier clears it (content review is "
                  "mechanical_review's job) — correctly caught the tier-conflation bug")
            sys.exit(1)
        print("ours=the over-reaching variant also cleared oracle=expected it to veto "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)
    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real regression fixture, end to end ---------------

d_wrong = toy_cycle_project(WRONG_SOLUTION)
cycle = build_cycle_snapshot(d_wrong, "HEAD", ["O6-1"], include_existing_traps=True)

# 1. The mechanical tier re-executes the SAME probe against the SAME wrong
# solution in a fresh, isolated checkout — no drift, no state leakage — so it
# correctly does NOT catch the correlated-authorship defect. This is by
# design (R5): mechanical catches a different bug class.
v_mech = MechanicalGovernor().audit(cycle)
check("the mechanical tier does NOT catch the O6 replay (by design)", v_mech.is_clear is True)

# 2. The review tier — a single decorrelated pass over the whole batch —
# DOES catch it, vetoing with a captured reason.
reviewer = Path(tempfile.mkdtemp(prefix="dc4-reviewer-")) / "reviewer.py"
reviewer.write_text(REVIEW_REVEALS_THE_BUG)
actor_provenance = metadata_verified("claude-sonnet-5")
governor = MechanicalReviewGovernor(actor_provenance, cmd=f"python3 {reviewer}")
v_review = governor.audit(cycle)
check("the review tier catches the O6 replay and vetoes", v_review.is_clear is False
      and "O6-1" in v_review.vetoes)
check("the veto carries a real, re-checkable reason (never a bare rejection)",
      "attempted" in v_review.vetoes["O6-1"])

# 3. The veto becomes a REAL captured trap on the vetoed claim (R5's
# constraint against an opaque second authority) — proven via the EXISTING,
# untouched capture() rule: the failure-inclusion check the veto names is RED
# on the wrong solution and GREEN on a correct one.
def failure_inclusion_check(repo_dir: Path) -> bool:
    r = subprocess.run(
        ["python3", "-c",
         "import sys; sys.path.insert(0, '.'); from solution import task_func; "
         "r = task_func(['a','b','c'], should_fail=['b']); "
         "sys.exit(0 if r == ['a','b','c'] else 1)"],
        cwd=repo_dir / "claims" / "s", capture_output=True, text=True)
    return r.returncode == 0


trap_red_on_wrong = not failure_inclusion_check(d_wrong)
d_correct = toy_cycle_project(CORRECT_SOLUTION)
trap_green_on_real = failure_inclusion_check(d_correct)
check("the veto's underlying check is RED on the wrong solution", trap_red_on_wrong is True)
check("the veto's underlying check is GREEN on the correct solution", trap_green_on_real is True)
check("capture() accepts the veto's reason as a legitimate, discriminating trap "
      "— a new counterexample on O6-1, not a bare rejection",
      capture(trap_red_on_wrong, trap_green_on_real) is True)

print("the O6 run-level replay is caught: every claim's own gate was green (correlated "
      "authorship); the mechanical tier correctly does NOT catch it (that's not its job); "
      "the review tier does, vetoing with a reason that capture() validates as a real, "
      "re-checkable trap on the vetoed claim — not an opaque second authority")
sys.exit(0)
PYEOF
