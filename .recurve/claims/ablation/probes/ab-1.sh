#!/usr/bin/env bash
# AB-1: the two ports exist; nothing existing changes
# (docs/plans/ablation-infra.md AI1). RED-first: until
# recurvelib.loop.reviewers exists the probe is RED.
#
# With $TRAP_FIXTURE: a `scenario` naming which regression to check. A
# capture-rule truth-table disagreement, or a candidate verdict type carrying
# a bypass field, must be caught (RED = still discriminating).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import dataclasses
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    from recurvelib.loop.runtime import capture, within_boundary, World, Actor, guarded_propose
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.loop.reviewers import (
        Adversary, Governor, AdversaryVerdict, GovernorVerdict, has_bypass_field,
    )
except ImportError:
    print("ours=no recurvelib.loop.reviewers yet oracle=Adversary/Governor ports exist")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if (Path(fixture) / "broken_capture.py").exists():
    # A candidate (deliberately wrong) capture() — the canonical truth table
    # it must uphold. A regression of this shape must be caught, RED.
    spec = importlib.util.spec_from_file_location("bcap", Path(fixture) / "broken_capture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    broken_capture = mod.capture
    table = {(True, True): True, (True, False): False,
             (False, True): False, (False, False): False}
    for (red_on_wrong, green_on_real), want in table.items():
        got = broken_capture(red_on_wrong, green_on_real)
        if got != want:
            print(f"ours=capture({red_on_wrong},{green_on_real})={got} oracle={want} "
                  f"— capture-rule regression correctly caught")
            sys.exit(1)
    print("ours=candidate capture() agrees on every cell oracle=at least one disagreement "
          "(fixture's broken candidate slipped through)")
    sys.exit(0)

if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()

    if scenario == "bypass_field_candidate":
        # A candidate verdict type smuggling a direct-certify field.
        @dataclasses.dataclass(frozen=True)
        class _BrokenVerdict:
            objection: object = None
            certified: bool = False   # the bypass: certifies GREEN directly

        hit = has_bypass_field(_BrokenVerdict)
        if hit is None:
            print("ours=no bypass field flagged oracle=certified must be caught "
                  "(fixture's gaming candidate slipped through)")
            sys.exit(0)
        print(f"has_bypass_field correctly flags {hit!r} on a candidate that bypasses capture()")
        sys.exit(1)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. World/Actor/capture/within_boundary/guarded_propose still importable and
# behaviorally unchanged (capture's own truth table, spot-checked).
check("capture(True, True) == True", capture(True, True) is True)
check("capture(True, False) == False", capture(True, False) is False)
check("capture(False, True) == False", capture(False, True) is False)
check("capture(False, False) == False", capture(False, False) is False)

# 2. the two new ports exist as Protocols with the documented method names.
check("Adversary has .review", hasattr(Adversary, "review"))
check("Governor has .audit", hasattr(Governor, "audit"))

# 3. neither real verdict type carries a bypass-shaped field.
check("AdversaryVerdict carries no bypass field", has_bypass_field(AdversaryVerdict) is None)
check("GovernorVerdict carries no bypass field", has_bypass_field(GovernorVerdict) is None)

# 4. the verdict constructors produce the documented shapes only.
av = AdversaryVerdict.no_objection()
check("no_objection is clean", av.is_clean is True)
av2 = AdversaryVerdict.proposed_trap("fixtures/x", "found a counterexample")
check("proposed_trap is not clean", av2.is_clean is False)
gv = GovernorVerdict.cleared()
check("cleared is clear", gv.is_clear is True)
gv2 = GovernorVerdict.veto({"X-1": "drift detected"})
check("veto carries the reason", gv2.vetoes == {"X-1": "drift detected"} and gv2.is_clear is False)
gv3 = GovernorVerdict.pending_human_signoff()
check("pending_human_signoff is pending, not clear", gv3.pending is True and gv3.is_clear is False)

print("Adversary/Governor ports exist alongside World/Actor; capture()/within_boundary/"
      "guarded_propose are untouched; neither verdict type can certify a claim directly")
sys.exit(0)
PYEOF
