#!/usr/bin/env bash
# AB-8: policy floor (AI9) + mechanical governor default-on (AI10).
# RED-first: until recurvelib.adapters.policy exists (or the config surface
# doesn't wire it) the probe is RED.
#
# With $TRAP_FIXTURE: a scenario asserting a suite-wide "off" default should
# suppress a claim's min_governor_tier floor — the real engine must refuse
# (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import sys
import tempfile
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

try:
    from recurvelib.core.config import load as load_config
    from recurvelib.core.model import Gap
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    from recurvelib.adapters.policy import (
        effective_governor_tier, DEFAULT_GOVERNOR_TIER, DEFAULT_ADVERSARY_TIER,
        InvalidTierError, GOVERNOR_TIERS,
    )
except ImportError:
    print("ours=no recurvelib.adapters.policy yet "
          "oracle=a claim's min_governor_tier floors the suite-wide governor default")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


def write_toml(d: Path, governor: str | None):
    body = (
        "[project]\nname = \"fixture\"\nlabel = \"suite\"\ndefault_reads = \"none\"\n"
        "cycles_dir = \"cycles\"\nschema = \"1\"\n\n[target]\ntree = \".\"\n\n"
        "[gate]\ntraps = \"required\"\nquality = \"pre-launch\"\n"
    )
    if governor is not None:
        body += f"governor = \"{governor}\"\n"
    body += "\n[reads.none]\nmethod = \"none\"\n\n[suites.s]\ndir = \"claims/s\"\n"
    (d / "recurve.toml").write_text(body)


if fixture:
    import importlib.util

    scenario = (Path(fixture) / "scenario").read_text().strip()
    if scenario == "suite_off_suppresses_claim_floor":
        spec = importlib.util.spec_from_file_location("bpol", Path(fixture) / "broken_policy.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        floored = mod.effective_governor_tier("off", min_governor_tier="human_required")
        if floored != "human_required":
            print(f"ours={floored!r} oracle='human_required' — the suite-wide 'off' default "
                  f"must not suppress the claim-level floor — correctly caught the suppression")
            sys.exit(1)
        print("ours=the broken policy still upheld the floor oracle=expected it to suppress "
              "(this fixture did not exercise the intended bug)")
        sys.exit(0)
    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. a claim with no floor uses the suite default exactly (no behavior change
# for the common case).
check("no floor -> suite default", effective_governor_tier("mechanical", "") == "mechanical")
check("no floor, off suite default -> off", effective_governor_tier("off", "") == "off")

# 2. AI9: a claim's floor holds regardless of a WEAKER suite-wide default.
check("a human_required floor holds under a weaker 'off' suite default",
      effective_governor_tier("off", "human_required") == "human_required")
check("a human_required floor holds under a weaker 'mechanical' suite default",
      effective_governor_tier("mechanical", "human_required") == "human_required")

# 3. a claim's floor never WEAKENS a stronger suite-wide default.
check("a weaker claim floor does not weaken a stronger suite default",
      effective_governor_tier("human_required", "mechanical") == "human_required")

# 4. an unknown tier name refuses, both as suite default and as a floor.
try:
    effective_governor_tier("not-a-real-tier", "")
    check("unknown suite default refused", False)
except InvalidTierError:
    pass
try:
    effective_governor_tier("mechanical", "not-a-real-tier")
    check("unknown floor refused", False)
except InvalidTierError:
    pass

# 5. AI10: [gate] governor defaults to "mechanical" in a fresh suite — no
# configuration step required to get it.
d = Path(tempfile.mkdtemp(prefix="ab8-proj-"))
(d / "claims" / "s").mkdir(parents=True)
write_toml(d, governor=None)  # no [gate] governor line at all
cfg = load_config(d / "recurve.toml")
check("a fresh suite's [gate] governor defaults to mechanical", cfg.gate_governor == "mechanical")
check("DEFAULT_GOVERNOR_TIER constant matches the config default",
      DEFAULT_GOVERNOR_TIER == "mechanical" == cfg.gate_governor)

# 6. an explicit [gate] governor overrides the default, validated.
d2 = Path(tempfile.mkdtemp(prefix="ab8-proj2-"))
(d2 / "claims" / "s").mkdir(parents=True)
write_toml(d2, governor="human_required")
cfg2 = load_config(d2 / "recurve.toml")
check("an explicit [gate] governor is honored", cfg2.gate_governor == "human_required")

# 7. [gate] adversary defaults to off (R2's bounds: opt-in, cost-aware).
check("[gate] adversary defaults to off", cfg.gate_adversary == "off" == DEFAULT_ADVERSARY_TIER)

# 8. a Gap's min_governor_tier field parses and validates.
suite_dir = d / "claims" / "s"
(suite_dir / "probes").mkdir(parents=True, exist_ok=True)
probe = suite_dir / "probes" / "p.sh"
probe.write_text("#!/usr/bin/env bash\nexit 0\n")
raw = {
    "id": "AB8-1", "title": "x", "class": "missing-surface", "status": "closed",
    "severity": "feature", "smallest_fix": "x", "probe": "probes/p.sh",
    "min_governor_tier": "human_required",
}
gap = Gap.parse(raw, "s", suite_dir, suite_dir / "gaps.yaml", ("none",), "none")
check("Gap.min_governor_tier parses", gap.min_governor_tier == "human_required")
check("the parsed floor resolves correctly against a weaker suite default",
      effective_governor_tier(cfg.gate_governor, gap.min_governor_tier) == "human_required")

raw_bad = dict(raw, min_governor_tier="not-a-real-tier")
try:
    Gap.parse(raw_bad, "s", suite_dir, suite_dir / "gaps.yaml", ("none",), "none")
    check("an unknown min_governor_tier is a parse error", False)
except Exception:
    pass

print("the mechanical governor tier is on by default in a fresh suite (AI10); a claim's "
      "min_governor_tier floors the effective tier regardless of a weaker suite-wide "
      "default, and never weakens a stronger one (AI9)")
sys.exit(0)
PYEOF
