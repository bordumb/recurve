#!/usr/bin/env bash
# DC-2: surface the weak-oracle question during authoring, not after
# (docs/plans/oracle-strength-and-decorrelation.md R3). RED-first: until
# recurvelib.analysis.oracle_tier.needs_oracle_advisory exists (or disagrees
# with the oracle below) the probe is RED.
#
# With $TRAP_FIXTURE: a `scenario` naming a gaming attempt — a reference field
# added purely to suppress the advisory, with `drill --diff` never actually
# run. The real engine must still surface the advisory (same shape as DC-1's
# anti-gaming traps — presence of the field is not evidence).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
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
    from recurvelib.analysis.oracle_tier import needs_oracle_advisory
except ImportError:
    print("ours=no needs_oracle_advisory yet oracle=authoring-time weak-oracle advisory")
    sys.exit(1)  # RED-first

cfg = load_config(find_config(Path(root)))
W = Path(tempfile.mkdtemp(prefix="dc2-"))
suite_dir = W / "suite"
(suite_dir / "probes").mkdir(parents=True)
source_file = suite_dir / "gaps.yaml"
source_file.write_text("[]\n")


def make_gap(gid, *, with_trap=True, reference_name=None, status=Status.CLOSED,
             oracle_waiver=""):
    probe = suite_dir / "probes" / f"{gid.lower()}.sh"
    probe.write_text("#!/usr/bin/env bash\nexit 0\n")
    if with_trap:
        trap_dir = suite_dir / "probes" / (probe.stem + ".trap") / "ce"
        trap_dir.mkdir(parents=True, exist_ok=True)
        (trap_dir / "marker").write_text("x")
    reference = None
    if reference_name:
        ref = suite_dir / reference_name
        ref.write_text("#!/usr/bin/env bash\nexit 0\n")
        reference = ref
    return Gap(
        id=gid, suite="synthetic-dc2", title="synthetic", gap_class=GapClass.MISSING_SURFACE,
        status=status, severity=Severity.FEATURE, evidence=(), observed="", smallest_fix="x",
        unlocks="", reads="none", covers=(), probe=probe, source_file=source_file,
        reference=reference, oracle_waiver=oracle_waiver,
    )


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


if fixture:
    scenario = (Path(fixture) / "scenario").read_text().strip()
    if scenario == "reference_added_to_suppress":
        g = make_gap("DC2-T1", reference_name="reference.sh")
        advisory = needs_oracle_advisory(g, cfg, evidence=[])  # diff never actually run
        if not advisory:
            print("ours=advisory suppressed oracle=must still show — reference field alone "
                  "(diff never run) is not evidence (fixture's gaming claim succeeded)")
            sys.exit(0)  # a real regression: the guard failed to catch it
        print("a reference field with no recorded diff evidence does not suppress the advisory")
        sys.exit(1)
    print(f"unknown scenario: {scenario}")
    sys.exit(2)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. closed, trapped, no reference/adversary/waiver -> advisory shown.
g1 = make_gap("DC2-1")
check("bare trap_hardened closed claim gets the advisory", needs_oracle_advisory(g1, cfg, evidence=[]) is True)

# 2. closed, reference set AND diff actually ran -> no advisory (differential-checked).
g2 = make_gap("DC2-2", reference_name="reference.sh")
ev = [{"gap": "DC2-2", "check": "diff", "ran": True, "disagreement": False}]
check("a real diff pass suppresses the advisory", needs_oracle_advisory(g2, cfg, evidence=ev) is False)

# 3. closed with a declared oracle_waiver -> no advisory (the honest reason is already visible).
g3 = make_gap("DC2-3", oracle_waiver="no external oracle available for this claim")
check("a declared oracle_waiver suppresses the advisory", needs_oracle_advisory(g3, cfg, evidence=[]) is False)

# 4. an OPEN (not yet closed) claim never gets the advisory — it isn't a GREEN yet to qualify.
g4 = make_gap("DC2-4", status=Status.OPEN)
check("an open claim never gets the advisory", needs_oracle_advisory(g4, cfg, evidence=[]) is False)

# 5. rendering: `recurve ledger` surfaces the advisory footer for a bare claim.
from recurvelib.core.model import Ledger, SuiteLedger
ledger = Ledger(suites=(SuiteLedger(suite="synthetic-dc2", suite_dir=suite_dir, gaps=(g1,)),))
from recurvelib.io import render
table = render.ledger_table(ledger, cfg.label, cfg=cfg)
check("ledger renders the weak-oracle advisory footer", "weak-oracle advisory" in table and "DC2-1" in table)

print("the weak-oracle question surfaces at authoring/ledger time — advisory only, "
      "never blocking GREEN — and resists reference-field-without-a-real-pass gaming")
sys.exit(0)
PYEOF
