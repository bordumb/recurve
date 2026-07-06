#!/bin/bash
# FS-6: the campaign engine archives every candidate tried and halts on
# budget or on K consecutive rounds with no new record -- a measured stop,
# not an iteration count picked out of the air.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  IMPL="$TRAP_FIXTURE/campaign.py"
else
  IMPL="$ROOT/recurvelib/fansearch/campaign.py"
fi

python3 - "$ROOT" "$IMPL" <<'PYEOF'
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

root, impl_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

spec = importlib.util.spec_from_file_location("campaign_candidate", impl_path)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: campaign module failed to import: {e}")
    sys.exit(1)

with tempfile.TemporaryDirectory() as tmp:
    cfg = SimpleNamespace(state_dir=Path(tmp))

    # No target repo: every round is untested (nothing to gate-confirm
    # against), so the dry-generations count must still stop it exactly at
    # the configured threshold.
    summary = mod.run_campaign(cfg, "dyadic_lyapunov", ns_repo=None,
                               budget_seconds=30.0, dry_generations=2, seed0=0)
    if summary.rounds != 2:
        print(f"RED: expected exactly 2 rounds at dry_generations=2, got {summary.rounds}")
        sys.exit(1)
    if summary.stopped_reason != "dry_generations":
        print(f"RED: expected stopped_reason='dry_generations', got {summary.stopped_reason!r}")
        sys.exit(1)

    entries = mod.read_archive(mod.archive_path(cfg, "dyadic_lyapunov"))
    if len(entries) != 2:
        print(f"RED: archive should hold exactly 2 entries, has {len(entries)}")
        sys.exit(1)

    # The budget stop, independently: a near-zero budget must halt on the
    # very first check, before a second round ever runs.
    cfg2 = SimpleNamespace(state_dir=Path(tmp) / "budget-check")
    summary2 = mod.run_campaign(cfg2, "dyadic_lyapunov", ns_repo=None,
                                budget_seconds=0.0, dry_generations=1000, seed0=0)
    if summary2.stopped_reason != "budget":
        print(f"RED: expected stopped_reason='budget' at budget_seconds=0, "
              f"got {summary2.stopped_reason!r}")
        sys.exit(1)

print("GREEN: dry-generations and budget stops both trigger at their configured threshold; "
      "every round archived")
sys.exit(0)
PYEOF
