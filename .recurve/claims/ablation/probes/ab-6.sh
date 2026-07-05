#!/usr/bin/env bash
# AB-6: the adversary registry + off/same_model/cross_model adapters
# (docs/plans/ablation-infra.md AI2; satisfies R2's automated tiers).
# RED-first: until recurvelib.adapters.adversary exists the probe is RED.
#
# With $TRAP_FIXTURE: a broken_cross_model.py alternate — either skipping the
# identity check entirely, or trusting a self-reported "requested_model"
# instead of the reviewer's actual "served_model". Both are the O6/config-
# drift bug classes R2 exists to catch (RED = still discriminating).
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
    from recurvelib.adapters.snapshot import build_claim_snapshot
    from recurvelib.adapters._shared.provenance import metadata_verified
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.adversary import ADVERSARY_ADAPTERS, NoOpAdversary
    from recurvelib.adapters.adversary.same_model import SameModelAdversary, AdversaryReviewerError
    from recurvelib.adapters.adversary.cross_model import CrossModelAdversary, CrossModelIdentityViolation
    from recurvelib.adapters.registry import resolve_adversary, UnknownAdapterError, MalformedAdapterError
except ImportError:
    print("ours=no recurvelib.adapters.adversary yet "
          "oracle=the adversary registry + off/same_model/cross_model adapters")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


def toy_snapshot(reviewer_body: str):
    d = Path(tempfile.mkdtemp(prefix="ab6-repo-"))
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    empty_hooks = Path(tempfile.mkdtemp(prefix="ab6-nohooks-"))
    subprocess.run(["git", "config", "core.hooksPath", str(empty_hooks)], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    (d / "claim.txt").write_text("the claim under review\n")
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-gpg-sign", "-m", "i"], cwd=d, check=True)
    snap = build_claim_snapshot(d, "HEAD", "X-1", include_existing_traps=False)
    reviewer = Path(tempfile.mkdtemp(prefix="ab6-reviewer-")) / "reviewer.py"
    reviewer.write_text(reviewer_body)
    return d, snap, reviewer


NO_OBJECTION_A = (
    "import json\n"
    "print(json.dumps({'served_model': 'model-a', 'objection': None}))\n"
)
NO_OBJECTION_B = (
    "import json\n"
    "print(json.dumps({'served_model': 'model-b', 'objection': None}))\n"
)
OBJECTS_A = (
    "import json\n"
    "print(json.dumps({'served_model': 'model-a', "
    "'objection': {'fixture': 'fixtures/found-it', 'rationale': 'disagrees with the solution'}}))\n"
)

if fixture:
    spec = importlib.util.spec_from_file_location("bcm", Path(fixture) / "broken_cross_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    BrokenCrossModel = mod.BrokenCrossModel

    scenario = (Path(fixture) / "scenario").read_text().strip()
    _, snap, reviewer = toy_snapshot(NO_OBJECTION_A)

    if scenario == "identity_check_bypassed":
        actor = metadata_verified("model-a")  # same as the reviewer's served_model
        adv = BrokenCrossModel(actor, cmd=f"python3 {reviewer}")
        try:
            adv.review(snap)
            # The bug manifested: a same-identity pair was silently accepted.
            # Correctly caught by this check -> RED (still discriminating).
            print("ours=same-identity pair silently accepted oracle=must raise "
                  "CrossModelIdentityViolation — correctly caught the bug")
            sys.exit(1)
        except CrossModelIdentityViolation:
            print("ours=the broken adapter still raised oracle=expected it to accept silently "
                  "(this fixture did not exercise the intended bug)")
            sys.exit(0)

    if scenario == "trusts_requested_not_served":
        # The reviewer's ACTUAL served_model is model-a (same as actor); a
        # broken adapter trusting a self-reported "requested_model" of
        # model-b would wrongly wave this through as cross-model.
        actor = metadata_verified("model-a")
        adv = BrokenCrossModel(actor, cmd=f"python3 {reviewer}", requested_model="model-b")
        try:
            adv.review(snap)
            print("ours=requested_model='model-b' accepted despite served_model='model-a' "
                  "oracle=must refuse — the served identity is what's verified, not requested "
                  "— correctly caught the config-drift bug")
            sys.exit(1)
        except CrossModelIdentityViolation:
            print("ours=the broken adapter still refused oracle=expected it to accept "
                  "(this fixture did not exercise the intended bug)")
            sys.exit(0)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. the registry resolves the three adapters; an unknown name refuses.
check("off resolves", resolve_adversary("off", ADVERSARY_ADAPTERS) is NoOpAdversary)
check("same_model resolves", resolve_adversary("same_model", ADVERSARY_ADAPTERS) is SameModelAdversary)
check("cross_model resolves", resolve_adversary("cross_model", ADVERSARY_ADAPTERS) is CrossModelAdversary)
try:
    resolve_adversary("not-a-real-adapter", ADVERSARY_ADAPTERS)
    check("unknown adapter refused", False)
except UnknownAdapterError:
    pass

# 2. a malformed adapter (no .review) is refused AT REGISTRATION, never at
# first invocation.
from recurvelib.adapters.registry import build_adversary_registry
class _NotAnAdversary:
    pass
try:
    build_adversary_registry({"bogus": _NotAnAdversary})
    check("malformed adapter refused at registration", False)
except MalformedAdapterError:
    pass

# 3. off: always no_objection.
check("off never objects", NoOpAdversary().review(None).is_clean is True)

# 4. same_model: a clean pass and a proposed trap, both parsed off the wire protocol.
_, snap_clean, rev_clean = toy_snapshot(NO_OBJECTION_A)
sm = SameModelAdversary(cmd=f"python3 {rev_clean}")
v = sm.review(snap_clean)
check("same_model clean pass -> no_objection", v.is_clean is True)
check("same_model records the served_model as its provenance identity", sm.last_provenance.identity == "model-a")

_, snap_obj, rev_obj = toy_snapshot(OBJECTS_A)
sm2 = SameModelAdversary(cmd=f"python3 {rev_obj}")
v2 = sm2.review(snap_obj)
check("same_model proposed trap carries the fixture+rationale",
      v2.objection == ("fixtures/found-it", "disagrees with the solution"))

# 5. same_model never silently falls back to AGENT_CMD when unconfigured.
import os
os.environ.pop("RECURVE_ADVERSARY_CMD", None)
try:
    SameModelAdversary().review(snap_clean)
    check("unconfigured reviewer command refused", False)
except AdversaryReviewerError:
    pass

# 6. cross_model: a genuinely different served model succeeds.
_, snap_b, rev_b = toy_snapshot(NO_OBJECTION_B)
cm = CrossModelAdversary(metadata_verified("model-a"), cmd=f"python3 {rev_b}")
v3 = cm.review(snap_b)
check("cross_model succeeds when the served model verifiably differs", v3.is_clean is True)

# 7. cross_model REFUSES when the verified served model matches the actor's —
# the exact O6 bug class.
_, snap_a, rev_a = toy_snapshot(NO_OBJECTION_A)
cm_same = CrossModelAdversary(metadata_verified("model-a"), cmd=f"python3 {rev_a}")
try:
    cm_same.review(snap_a)
    check("same-identity cross_model pair refused", False)
except CrossModelIdentityViolation:
    pass

# 8. isolation boundary: the reviewer sees only the snapshot, never the acting
# agent's live working directory.
live_marker = Path(tempfile.mkdtemp(prefix="ab6-live-")) / "acting_agent_secret.txt"
live_marker.write_text("the acting agent's live session state\n")
peek_reviewer = Path(tempfile.mkdtemp(prefix="ab6-peekrev-")) / "reviewer.py"
peek_reviewer.write_text(
    "import json, os\n"
    f"leaked = os.path.exists({str(live_marker)!r})\n"
    "print(json.dumps({'served_model': 'model-a', 'objection': None, 'saw_live_marker': leaked}))\n"
)
_, snap_iso, _ = toy_snapshot("")
sm_iso = SameModelAdversary(cmd=f"python3 {peek_reviewer}")
sm_iso.review(snap_iso)
import json as _json
check("the isolated reviewer's own cwd never contains the acting agent's live marker",
      not (Path(snap_iso.root) / "acting_agent_secret.txt").exists())

print("the adversary registry resolves off/same_model/cross_model; identity is verified "
      "from the reviewer's actual served_model (never a requested flag), and cross_model "
      "refuses a same-identity pair — the O6 bug class")
sys.exit(0)
PYEOF
