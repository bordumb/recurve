#!/usr/bin/env bash
# AB-7: the governor registry + off/mechanical/mechanical_review adapters
# (docs/plans/ablation-infra.md AI2; satisfies R5's automated tiers).
# RED-first: until recurvelib.adapters.governor exists the probe is RED.
#
# With $TRAP_FIXTURE: a broken_mechanical.py that always clears regardless of
# re-execution (state-leakage bug), or a broken_mechanical_review.py that
# skips the identity check. Both are R5's counterexamples (RED = caught).
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
    from recurvelib.adapters.snapshot import build_cycle_snapshot
    from recurvelib.adapters._shared.provenance import metadata_verified
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.governor import GOVERNOR_ADAPTERS, NoOpGovernor
    from recurvelib.adapters.governor.mechanical import MechanicalGovernor
    from recurvelib.adapters.governor.mechanical_review import (
        MechanicalReviewGovernor, GovernorReviewerError, GovernorIdentityViolation,
    )
    from recurvelib.adapters.registry import resolve_governor, UnknownAdapterError
except ImportError:
    print("ours=no recurvelib.adapters.governor yet "
          "oracle=the governor registry + off/mechanical/mechanical_review adapters")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


def toy_project(*, probe_body: str):
    """A minimal recurve project: one suite `s`, one claim `X-1` whose probe
    is `probe_body` (a bash script), with a real trap. Committed."""
    d = Path(tempfile.mkdtemp(prefix="ab7-repo-"))
    (d / "claims" / "s" / "probes").mkdir(parents=True)
    (d / "recurve.toml").write_text(
        "[project]\nname = \"fixture\"\nlabel = \"suite\"\ndefault_reads = \"none\"\n"
        "cycles_dir = \"cycles\"\nschema = \"1\"\n\n[target]\ntree = \".\"\n\n"
        "[gate]\ntraps = \"required\"\nquality = \"pre-launch\"\n\n"
        "[reads.none]\nmethod = \"none\"\n\n[suites.s]\ndir = \"claims/s\"\n"
    )
    probe = d / "claims" / "s" / "probes" / "x-1.sh"
    probe.write_text(probe_body)
    probe.chmod(0o755)
    trap_dir = d / "claims" / "s" / "probes" / "x-1.trap" / "ce"
    trap_dir.mkdir(parents=True)
    (trap_dir / "marker").write_text("x\n")
    (d / "claims" / "s" / "gaps.yaml").write_text(
        "- id: X-1\n  title: toy claim\n  class: missing-surface\n  status: closed\n"
        "  severity: feature\n  reads: none\n  evidence: [\"x:1\"]\n"
        "  observed: GREEN by construction\n  smallest_fix: none\n  probe: probes/x-1.sh\n"
    )
    (d / "claims" / "s" / "GAPS.md").write_text("## X-1\n")
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    empty_hooks = Path(tempfile.mkdtemp(prefix="ab7-nohooks-"))
    subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-gpg-sign", "-m", "i"], cwd=d, check=True)
    return d


REAL_GREEN_PROBE = (
    "#!/usr/bin/env bash\n"
    "if [ -n \"${TRAP_FIXTURE:-}\" ]; then echo counterexample; exit 1; fi\n"
    "echo ok; exit 0\n"
)
SECRETLY_BROKEN_PROBE = (
    "#!/usr/bin/env bash\n"
    "echo 'actually red on re-execution'; exit 1\n"
)

NO_VETO_REVIEWER = (
    "import json\n"
    "print(json.dumps({'served_model': 'model-a', 'vetoes': {}}))\n"
)
VETO_REVIEWER = (
    "import json\n"
    "print(json.dumps({'served_model': 'model-a', "
    "'vetoes': {'X-1': 'shares the actor blind spot'}}))\n"
)


def write_reviewer(body: str) -> Path:
    p = Path(tempfile.mkdtemp(prefix="ab7-reviewer-")) / "reviewer.py"
    p.write_text(body)
    return p


if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()

    if scenario == "mechanical_always_clears":
        spec = importlib.util.spec_from_file_location("bmech", Path(fixture) / "broken_mechanical.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d = toy_project(probe_body=SECRETLY_BROKEN_PROBE)
        cycle = build_cycle_snapshot(d, "HEAD", ["X-1"], include_existing_traps=True)
        v = mod.BrokenMechanicalGovernor().audit(cycle)
        if v.is_clear:
            print("ours=cleared despite RED-on-re-execution oracle=must veto — "
                  "correctly caught the state-leakage bug")
            sys.exit(1)
        print("ours=the broken governor still vetoed oracle=expected it to clear "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)

    if scenario == "review_skips_identity_check":
        spec = importlib.util.spec_from_file_location(
            "bmrev", Path(fixture) / "broken_mechanical_review.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d = toy_project(probe_body=REAL_GREEN_PROBE)
        cycle = build_cycle_snapshot(d, "HEAD", ["X-1"], include_existing_traps=True)
        reviewer = write_reviewer(NO_VETO_REVIEWER)
        actor = metadata_verified("model-a")  # same as the reviewer's served_model
        adv = mod.BrokenMechanicalReviewGovernor(actor, cmd=f"python3 {reviewer}")
        try:
            adv.audit(cycle)
            print("ours=same-identity review-tier pass silently cleared "
                  "oracle=must raise GovernorIdentityViolation — correctly caught the bug")
            sys.exit(1)
        except GovernorIdentityViolation:
            print("ours=the broken governor still raised oracle=expected it to clear silently "
                  "(this fixture did not exercise the intended bug)")
            sys.exit(0)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. the registry resolves the three adapters; an unknown name refuses.
check("off resolves", resolve_governor("off", GOVERNOR_ADAPTERS) is NoOpGovernor)
check("mechanical resolves", resolve_governor("mechanical", GOVERNOR_ADAPTERS) is MechanicalGovernor)
check("mechanical_review resolves",
      resolve_governor("mechanical_review", GOVERNOR_ADAPTERS) is MechanicalReviewGovernor)
try:
    resolve_governor("not-a-real-governor", GOVERNOR_ADAPTERS)
    check("unknown governor refused", False)
except UnknownAdapterError:
    pass

# 2. off: always cleared.
check("off always clears", NoOpGovernor().audit(None).is_clear is True)

# 3. mechanical: a genuinely green, trap-hardened claim clears on re-execution.
d_good = toy_project(probe_body=REAL_GREEN_PROBE)
cycle_good = build_cycle_snapshot(d_good, "HEAD", ["X-1"], include_existing_traps=True)
v_good = MechanicalGovernor().audit(cycle_good)
check("mechanical clears a claim that re-executes GREEN with its trap RED", v_good.is_clear is True)

# 4. mechanical: a claim whose probe is secretly RED on re-execution (state
# leakage — "works in this working directory") is vetoed, with a captured
# reason (never a bare rejection).
d_bad = toy_project(probe_body=SECRETLY_BROKEN_PROBE)
cycle_bad = build_cycle_snapshot(d_bad, "HEAD", ["X-1"], include_existing_traps=True)
v_bad = MechanicalGovernor().audit(cycle_bad)
check("mechanical vetoes a claim that is RED on fresh re-execution", v_bad.is_clear is False
      and "X-1" in v_bad.vetoes and bool(v_bad.vetoes["X-1"]))

# 5. mechanical_review: a clean batch (no vetoes, verifiably different model)
# clears.
reviewer_clean = write_reviewer(NO_VETO_REVIEWER)
mr = MechanicalReviewGovernor(metadata_verified("model-b"), cmd=f"python3 {reviewer_clean}")
v_mr = mr.audit(cycle_good)
check("mechanical_review clears a clean, cross-identity batch", v_mr.is_clear is True)

# 6. mechanical_review: a batch the review-tier vetoes carries the reason
# (becomes a captured trap upstream — R5's requirement; this adapter's job is
# just to surface the reason).
reviewer_veto = write_reviewer(VETO_REVIEWER)
mr2 = MechanicalReviewGovernor(metadata_verified("model-b"), cmd=f"python3 {reviewer_veto}")
v_veto = mr2.audit(cycle_good)
check("mechanical_review's veto carries a reason, not a bare rejection",
      v_veto.vetoes == {"X-1": "shares the actor blind spot"})

# 7. mechanical_review REFUSES when the review pass's verified identity
# matches the cycle's own claim-authoring identity — the O6 shape, at the
# run level.
reviewer_same = write_reviewer(NO_VETO_REVIEWER)  # served_model = model-a
mr_same = MechanicalReviewGovernor(metadata_verified("model-a"), cmd=f"python3 {reviewer_same}")
try:
    mr_same.audit(cycle_good)
    check("same-identity review-tier pass refused", False)
except GovernorIdentityViolation:
    pass

# 8. mechanical_review never silently falls back to AGENT_CMD when
# RECURVE_GOVERNOR_CMD is unset.
import os
os.environ.pop("RECURVE_GOVERNOR_CMD", None)
try:
    MechanicalReviewGovernor(metadata_verified("model-a")).audit(cycle_good)
    check("unconfigured governor command refused", False)
except GovernorReviewerError:
    pass

print("the governor registry resolves off/mechanical/mechanical_review; mechanical catches "
      "state leakage via fresh re-execution (not correlated authorship, by design); "
      "mechanical_review catches a same-identity batch review, refusing rather than "
      "silently clearing")
sys.exit(0)
PYEOF
