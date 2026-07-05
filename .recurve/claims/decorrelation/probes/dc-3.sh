#!/usr/bin/env bash
# DC-3: the O6-incident regression fixture, at CLAIM level (R2's acceptance
# criterion). Replays the real shape recorded in eval/runs/o6/results.jsonl
# (claude-sonnet-5-A3-...: declared_done=true, gate_outcome="declared",
# terminal_state.stop_reason="gate_green", but oracle_verdict="fail" — the
# agent authored its own claim AND its own RED-first probe, closed GREEN,
# and BigCodeBench's held-out oracle says the solution is wrong). Uses the
# REAL cross_model adversary adapter (AB-6) + the REAL capture() rule
# (runtime.py) — not stubs.
#
# RED-first: until recurvelib.adapters.adversary.cross_model exists (or the
# mechanism fails to catch the replay) the probe is RED.
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
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # a stray __pycache__ must not dirty the toy repo

try:
    from recurvelib.loop.runtime import capture
    from recurvelib.adapters.snapshot import build_claim_snapshot
    from recurvelib.adapters._shared.provenance import metadata_verified
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.adversary.cross_model import CrossModelAdversary, CrossModelIdentityViolation
except ImportError:
    print("ours=no recurvelib.adapters.adversary.cross_model yet "
          "oracle=the O6 claim-level replay is caught by a cross_model adversary pass")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


# --- the O6 shape, faithfully replayed (mirrors eval/runs/o6/matrix.jsonl's
# BigCodeBench/13 FTP task: "return the filenames ATTEMPTED, even ones that
# failed" — the actual misreading class the real incident exhibited was
# conflating "succeeded" with "attempted"). ---------------------------------

WRONG_SOLUTION = (
    "def task_func(items, should_fail):\n"
    "    # BUG (the O6 misreading): only returns items that succeeded, silently\n"
    "    # dropping ones that failed — but the spec requires every ATTEMPTED\n"
    "    # item in the result, success or failure.\n"
    "    attempted = []\n"
    "    for it in items:\n"
    "        if it in should_fail:\n"
    "            continue  # dropped instead of recorded as attempted\n"
    "        attempted.append(it)\n"
    "    return attempted\n"
)

CORRECT_SOLUTION = (
    "def task_func(items, should_fail):\n"
    "    attempted = []\n"
    "    for it in items:\n"
    "        attempted.append(it)  # attempted regardless of outcome\n"
    "    return attempted\n"
)

# The SAME-MODEL self-authored probe: happy path only (no items fail) — this
# is the shared blind spot. It agrees wrong_solution is fine because it never
# exercises the one case where the misreading matters.
SELF_PROBE = (
    "import sys\n"
    "sys.path.insert(0, '.')\n"
    "from solution import task_func\n"
    "result = task_func(['a', 'b', 'c'], should_fail=[])\n"
    "sys.exit(0 if result == ['a', 'b', 'c'] else 1)\n"
)

# The cross-model adversary's reviewer: a DIFFERENT read of the same spec — it
# specifically exercises the failure case the self-probe never tried.
ADVERSARY_REVIEWER = (
    "import json, sys\n"
    "sys.path.insert(0, '.')\n"
    "from solution import task_func\n"
    "result = task_func(['a', 'b', 'c'], should_fail=['b'])\n"
    "if result == ['a', 'b', 'c']:\n"
    "    print(json.dumps({'served_model': 'adversary-model-x', 'objection': None}))\n"
    "else:\n"
    "    print(json.dumps({'served_model': 'adversary-model-x', 'objection': {\n"
    "        'fixture': 'failure-inclusion',\n"
    "        'rationale': (\"task_func drops item 'b' from the result on failure; the spec \"\n"
    "                      \"requires every ATTEMPTED item, success or failure — same shape \"\n"
    "                      \"as the O6 FTP-downloader incident's attempted-vs-succeeded misreading\"),\n"
    "    }}))\n"
)


def toy_claim_repo(solution_body: str):
    d = Path(tempfile.mkdtemp(prefix="dc3-repo-"))
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    empty_hooks = Path(tempfile.mkdtemp(prefix="dc3-nohooks-"))
    subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    (d / "solution.py").write_text(solution_body)
    (d / "self_probe.py").write_text(SELF_PROBE)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-gpg-sign", "-m", "i"], cwd=d, check=True)
    return d


if fixture:
    # $TRAP_FIXTURE: a "reviewer" that shares the SAME blind spot as the
    # actor (same_model shape) — proving cross_model specifically is
    # necessary, not just any second pass. If the same-blind-spot reviewer
    # were mistaken for a real check, the O6 replay would slip through.
    scenario = (Path(fixture) / "scenario").read_text().strip()
    if scenario == "same_blind_spot_reviewer_insufficient":
        d = toy_claim_repo(WRONG_SOLUTION)
        snap = build_claim_snapshot(d, "HEAD", "O6-CLAIM", include_existing_traps=False)
        same_blind_spot_reviewer = Path(tempfile.mkdtemp(prefix="dc3-samerev-")) / "reviewer.py"
        # Shares the actor's exact blind spot: happy path only, same served_model.
        same_blind_spot_reviewer.write_text(
            "import json, sys\nsys.path.insert(0, '.')\nfrom solution import task_func\n"
            "result = task_func(['a','b','c'], should_fail=[])\n"
            "print(json.dumps({'served_model': 'claude-sonnet-5', 'objection': None}))\n"
        )
        adv = CrossModelAdversary(metadata_verified("claude-sonnet-5"),
                                  cmd=f"python3 {same_blind_spot_reviewer}")
        try:
            adv.review(snap)
            print("ours=same-blind-spot reviewer accepted as cross_model "
                  "oracle=must refuse (identity check would have caught this)")
            sys.exit(0)
        except CrossModelIdentityViolation:
            print("cross_model correctly refuses a reviewer sharing the actor's own "
                  "served identity — the O6 replay cannot slip through via a fake cross-model pass")
            sys.exit(1)
    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real regression fixture, end to end ---------------

# 1. Reproduce the incident: the self-authored probe alone says GREEN on the
# wrong solution — recurve's own gate, unaided, would have closed this claim.
d_wrong = toy_claim_repo(WRONG_SOLUTION)
self_probe_result = subprocess.run(
    ["python3", "self_probe.py"], cwd=d_wrong, capture_output=True, text=True)
check("the self-authored probe alone is GREEN on the wrong solution (reproduces O6)",
      self_probe_result.returncode == 0)

# 2. Run the REAL cross_model adversary against it.
snap = build_claim_snapshot(d_wrong, "HEAD", "O6-CLAIM", include_existing_traps=False)
reviewer = Path(tempfile.mkdtemp(prefix="dc3-reviewer-")) / "reviewer.py"
reviewer.write_text(ADVERSARY_REVIEWER)
actor_provenance = metadata_verified("claude-sonnet-5")  # the actor that wrote both halves
adv = CrossModelAdversary(actor_provenance, cmd=f"python3 {reviewer}")
verdict = adv.review(snap)
check("the cross_model adversary disagrees — it does NOT silently pass",
      verdict.is_clean is False)
check("the disagreement names a concrete, re-checkable fixture and rationale",
      verdict.objection[0] == "failure-inclusion" and "attempted" in verdict.objection[1])

# 3. Prove the disagreement is REAL evidence, not noise: the proposed
# counterexample is RED on the wrong solution and GREEN on a correct one —
# capture() (the EXISTING, untouched rule) accepts it as a legitimate trap.
def failure_inclusion_check(repo_dir: Path) -> bool:
    """True iff task_func includes a failing item in its result (the
    spec's actual requirement) — the exact check the adversary proposed."""
    r = subprocess.run(
        ["python3", "-c",
         "import sys; sys.path.insert(0, '.'); from solution import task_func; "
         "r = task_func(['a','b','c'], should_fail=['b']); "
         "sys.exit(0 if r == ['a','b','c'] else 1)"],
        cwd=repo_dir, capture_output=True, text=True)
    return r.returncode == 0


trap_red_on_wrong = not failure_inclusion_check(d_wrong)     # must be RED (fails) on the wrong solution
d_correct = toy_claim_repo(CORRECT_SOLUTION)
trap_green_on_real = failure_inclusion_check(d_correct)      # must be GREEN (passes) on the real fix
check("the proposed counterexample is RED on the wrong solution", trap_red_on_wrong is True)
check("the proposed counterexample is GREEN on the correct solution", trap_green_on_real is True)
check("capture() accepts the adversary's proposal as a legitimate, discriminating trap",
      capture(trap_red_on_wrong, trap_green_on_real) is True)

print("the O6 claim-level replay is caught: a same-model self-authored probe alone says "
      "GREEN, but the real cross_model adversary disagrees, and its proposed counterexample "
      "is validated by the EXISTING capture() rule as genuine evidence — not a silent pass, "
      "not noise")
sys.exit(0)
PYEOF
