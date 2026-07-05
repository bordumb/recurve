#!/usr/bin/env bash
# DC-1: oracle tier is recorded, derived, rendered — and honest about what
# backs it (docs/plans/oracle-strength-and-decorrelation.md R1). RED-first:
# until recurvelib.analysis.oracle_tier exists the probe is RED.
#
# With $TRAP_FIXTURE: a `scenario` file names a gaming attempt (a claim that
# the real engine would grant a stronger tier / accept a hand-set tier than
# it should). The probe runs the REAL, unmodified engine against the
# scenario and compares its actual behavior to the claimed one — same shape
# as toolkit/probes/tk-28.sh's ours-vs-oracle comparison. A correct engine
# disagrees with every gaming claim -> exit 1 (RED, still discriminating).
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
    from recurvelib.core.model import Gap, GapClass, Status, Severity
    from recurvelib.core.config import load as load_config, find_config
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.analysis.oracle_tier import (
        OracleTier, derive_tier, record_evidence, load_evidence,
        is_mechanical_reference, needs_oracle_advisory,
    )
except ImportError:
    print("ours=no recurvelib.analysis.oracle_tier yet oracle=tier recorded, derived, rendered")
    sys.exit(1)  # RED-first: the module does not exist

cfg = load_config(find_config(Path(root)))
W = Path(tempfile.mkdtemp(prefix="dc1-"))
suite_dir = W / "suite"
(suite_dir / "probes").mkdir(parents=True)
source_file = suite_dir / "gaps.yaml"
source_file.write_text("[]\n")


def make_gap(gid, *, probe_name="p.sh", with_trap=False, reference_name=None,
             status=Status.CLOSED):
    probe = suite_dir / "probes" / probe_name
    probe.write_text("#!/usr/bin/env bash\nexit 0\n")
    if with_trap:
        trap_dir = suite_dir / "probes" / (Path(probe_name).stem + ".trap") / "ce"
        trap_dir.mkdir(parents=True, exist_ok=True)
        (trap_dir / "marker").write_text("x")
    reference = None
    if reference_name:
        reference = suite_dir / reference_name
    return Gap(
        id=gid, suite="synthetic-dc1", title="synthetic", gap_class=GapClass.MISSING_SURFACE,
        status=status, severity=Severity.FEATURE, evidence=(), observed="", smallest_fix="x",
        unlocks="", reads="none", covers=(), probe=probe, source_file=source_file,
        reference=reference,
    )


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()

    if scenario == "reference_never_run":
        # reference set, but no diff evidence recorded anywhere for this gap.
        (suite_dir / "reference.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        g = make_gap("DC1-T1", with_trap=True, reference_name="reference.sh")
        actual = derive_tier(g, cfg, evidence=[])
        claimed = OracleTier.DIFFERENTIAL_CHECKED_LLM
        if actual == claimed:
            print(f"ours={actual.value} oracle=must NOT grant a differential tier — "
                  f"diff never ran (fixture's gaming claim succeeded)")
            sys.exit(0)  # a real regression: the guard failed to catch it
        print(f"reference field alone (no diff evidence) does not grant "
              f"{claimed.value}; actual={actual.value}")
        sys.exit(1)

    if scenario == "llm_reference_claims_mechanical":
        # reference is LLM-authored (contains a model-invocation marker) but
        # gamed into the mechanical allowlist — content must still win.
        ref = suite_dir / "reference.sh"
        ref.write_text("#!/usr/bin/env bash\n# calls anthropic to grade\nexit 0\n")
        cfg_gamed = cfg
        object.__setattr__(cfg_gamed, "mechanical_references", ("reference.sh",)) \
            if hasattr(cfg_gamed, "mechanical_references") else None
        g = make_gap("DC1-T2", with_trap=True, reference_name="reference.sh")
        mech = is_mechanical_reference(g, cfg_gamed)
        if mech:
            print("ours=mechanical oracle=must NOT be mechanical — reference's own "
                  "source invokes a model (gaming claim succeeded)")
            sys.exit(0)
        print("an LLM-authored reference is never mechanical, however it's configured "
              f"(is_mechanical_reference={mech})")
        sys.exit(1)

    if scenario == "hand_set_tier_rejected":
        raw = {
            "id": "DC1-T3", "title": "x", "class": "missing-surface", "status": "closed",
            "severity": "feature", "smallest_fix": "x", "probe": "probes/p.sh",
            "tier": "kernel_verified",
        }
        (suite_dir / "probes" / "p.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        try:
            Gap.parse(raw, "synthetic-dc1", suite_dir, source_file, ("none",), "none")
            print("ours=parse accepted a hand-set tier oracle=must raise GapParseError "
                  "(gaming claim succeeded)")
            sys.exit(0)
        except Exception:
            print("Gap.parse refuses a hand-set 'tier' key")
            sys.exit(1)

    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. no trap -> self_probe
g_self = make_gap("DC1-1", with_trap=False)
check("no-trap gap derives self_probe", derive_tier(g_self, cfg, evidence=[]) == OracleTier.SELF_PROBE)

# 2. trap present, no other evidence -> trap_hardened (today's baseline meaning)
g_trap = make_gap("DC1-2", with_trap=True)
check("trapped gap derives trap_hardened", derive_tier(g_trap, cfg, evidence=[]) == OracleTier.TRAP_HARDENED)

# 3. fuzz evidence recorded -> fuzz_measured
ev_fuzz = [{"gap": "DC1-3", "check": "fuzz", "ran": True}]
g_fuzz = make_gap("DC1-3", with_trap=True)
check("fuzz evidence upgrades to fuzz_measured",
      derive_tier(g_fuzz, cfg, evidence=ev_fuzz) == OracleTier.FUZZ_MEASURED)

# 4. reference + diff evidence, LLM-kind reference -> differential_checked_llm
(suite_dir / "ref_llm.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
g_diff_llm = make_gap("DC1-4", with_trap=True, reference_name="ref_llm.sh")
ev_diff = [{"gap": "DC1-4", "check": "diff", "ran": True, "disagreement": False}]
check("diff-checked LLM reference derives differential_checked_llm",
      derive_tier(g_diff_llm, cfg, evidence=ev_diff) == OracleTier.DIFFERENTIAL_CHECKED_LLM)

# 5. reference + diff evidence, mechanical-kind reference (allowlisted, no LLM
# markers in its own source) -> differential_checked_mechanical
(suite_dir / "ref_mech.sh").write_text("#!/usr/bin/env bash\n/usr/bin/python3 -m json.tool\nexit 0\n")
mech_cfg_dict = dict(mechanical_references=("ref_mech.sh",))
from dataclasses import replace as _replace
try:
    cfg_mech = _replace(cfg, **mech_cfg_dict)
except TypeError:
    print("ours=Config has no mechanical_references field yet oracle=[gate] mechanical_references configurable")
    sys.exit(1)
g_diff_mech = make_gap("DC1-5", with_trap=True, reference_name="ref_mech.sh")
ev_diff_mech = [{"gap": "DC1-5", "check": "diff", "ran": True, "disagreement": False}]
check("diff-checked mechanical reference derives differential_checked_mechanical",
      derive_tier(g_diff_mech, cfg_mech, evidence=ev_diff_mech) == OracleTier.DIFFERENTIAL_CHECKED_MECHANICAL)

# 6. hand-set tier field is rejected at parse time
raw_bad = {
    "id": "DC1-6", "title": "x", "class": "missing-surface", "status": "closed",
    "severity": "feature", "smallest_fix": "x", "probe": "probes/p.sh", "tier": "self_probe",
}
try:
    Gap.parse(raw_bad, "synthetic-dc1", suite_dir, source_file, ("none",), "none")
    print("ours=parse accepted a hand-set tier oracle=GapParseError")
    sys.exit(1)
except Exception as e:
    check("hand-set tier is a parse error, not a silent accept",
          "tier" in str(e).lower())

# 7. an EXISTING real ledger claim (toolkit's TK-1) with no fuzz/diff/adversary
# evidence derives trap_hardened by default (the migration bound: existing
# ledgers need no changes).
from recurvelib.core.model import load_ledger
real_ledger = load_ledger(cfg)
tk1 = real_ledger.by_id("TK-1")
check("TK-1 exists in the real ledger", tk1 is not None)
check("an existing claim with a trap and no other evidence defaults to trap_hardened",
      derive_tier(tk1, cfg, evidence=[]) == OracleTier.TRAP_HARDENED)

# 8. rendering: recurve ledger / recurve show carry the tier
from recurvelib.io import render
table = render.ledger_table(real_ledger, cfg.label, cfg=cfg)
check("ledger_table renders a tier for TK-1", "trap_hardened" in table)
detail = render.gap_detail(tk1, cfg.label, cfg=cfg)
check("gap_detail renders an oracle_tier line", "oracle_tier" in detail and "trap_hardened" in detail)

print("oracle tier is recorded, derived from real evidence (never hand-set), and rendered "
      "in ledger + show; the mechanical/LLM reference split is content-verified")
sys.exit(0)
PYEOF
