#!/usr/bin/env bash
# AB-9: one challenge_event schema, not two (docs/plans/ablation-infra.md
# AI8) — folds R4's reversal event and R5's veto event.
# RED-first: until recurvelib.adapters.challenge_event exists the probe is RED.
#
# With $TRAP_FIXTURE: an event authored in the OLD, separate reversal/veto
# shape. validate_challenge_event must refuse it (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import json
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    from recurvelib.core.config import load as load_config
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.challenge_event import (
        make_challenge_event, validate_challenge_event, ChallengeLog, ChallengeEventError, PHASES,
    )
except ImportError:
    print("ours=no recurvelib.adapters.challenge_event yet "
          "oracle=one unified challenge_event schema, folding R4's reversal + R5's veto")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()
    legacy_event = json.loads((Path(fixture) / "legacy_event.json").read_text())
    if scenario == "legacy_shape_rejected":
        try:
            validate_challenge_event(legacy_event)
            print(f"ours=legacy event accepted oracle=must refuse the old separate "
                  f"reversal/veto shape (fixture's gaming attempt succeeded)")
            sys.exit(0)
        except ChallengeEventError:
            print("validate_challenge_event correctly refuses the legacy reversal/veto shape")
            sys.exit(1)
    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. a veto (pre_publication) and a reversal (post_publication) are the SAME
# constructor/schema, differing only by phase.
veto = make_challenge_event(claim_id="X-1", phase="pre_publication",
                            tier_at_challenge="trap_hardened",
                            reason="mechanical_review vetoed: shares the actor blind spot")
reversal = make_challenge_event(claim_id="X-2", phase="post_publication",
                                tier_at_challenge="adversary_reviewed",
                                reason="a later differential pass falsified this GREEN")
check("veto and reversal share one schema", veto["schema"] == reversal["schema"])
check("phase distinguishes pre/post publication", veto["phase"] == "pre_publication"
      and reversal["phase"] == "post_publication")
validate_challenge_event(veto)
validate_challenge_event(reversal)

# 2. reason is required — a bare rejection is refused at construction time.
try:
    make_challenge_event(claim_id="X-3", phase="pre_publication",
                         tier_at_challenge="trap_hardened", reason="")
    check("empty reason refused", False)
except ChallengeEventError:
    pass

# 3. an unknown phase is refused.
try:
    make_challenge_event(claim_id="X-4", phase="mid_publication",
                         tier_at_challenge="trap_hardened", reason="x")
    check("unknown phase refused", False)
except ChallengeEventError:
    pass

# 4. a human attestation reference rides along when the challenger was human
# (AI6's tie-in) — additive, optional.
human_veto = make_challenge_event(claim_id="X-5", phase="pre_publication",
                                  tier_at_challenge="trap_hardened",
                                  reason="contradicts a peer-reviewed result",
                                  human_attestation_ref="attestations/human-approval-abc123.json")
check("a human attestation reference is carried when present",
      human_veto["human_attestation_ref"] == "attestations/human-approval-abc123.json")

# 5. ChallengeLog: append-only, one file per suite, combined rate.
d = Path(tempfile.mkdtemp(prefix="ab9-proj-"))
(d / "claims" / "s").mkdir(parents=True)
(d / "recurve.toml").write_text(
    "[project]\nname = \"fixture\"\nlabel = \"suite\"\ndefault_reads = \"none\"\n"
    "cycles_dir = \"cycles\"\nschema = \"1\"\n\n[target]\ntree = \".\"\n\n"
    "[gate]\ntraps = \"required\"\nquality = \"pre-launch\"\n\n"
    "[reads.none]\nmethod = \"none\"\n\n[suites.s]\ndir = \"claims/s\"\n"
)
cfg = load_config(d / "recurve.toml")
log = ChallengeLog(cfg, "s")
check("a fresh log has zero challenges", log.combined_rate(total_closed=10) == 0.0)
log.append(veto)
log.append(reversal)
check("appended events are readable back", len(log.events()) == 2)
check("combined_rate divides by total_closed", log.combined_rate(total_closed=10) == 0.2)
check("events_by_phase slices correctly",
      len(log.events_by_phase("pre_publication")) == 1
      and len(log.events_by_phase("post_publication")) == 1)

# 6. the log itself refuses an append in the legacy shape.
try:
    log.append({"reversal": True, "claim_id": "X-6"})
    check("legacy-shaped append refused", False)
except ChallengeEventError:
    pass

print("challenge_event unifies R4's reversal and R5's veto into one schema — phase "
      "distinguishes pre/post publication, reason is always required, and the old "
      "separate shapes are refused outright")
sys.exit(0)
PYEOF
