#!/bin/bash
# FS-9: the ablation switch (eval-full.md arm A11) is genuinely inert by
# default -- [fansearch] proxy = "off" is not just a config default, the
# core burndown loop (recurvelib/loop, cli/commands/matrix, run, ...)
# never references the fansearch subsystem at all, so turning it on is
# the only thing that can differ between A3 and A11.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  SEARCH_ROOT="$TRAP_FIXTURE"
else
  SEARCH_ROOT="$ROOT/recurvelib"
fi

# Structural check: no reference to the fansearch seam outside its own
# files. A grep-style assertion is appropriate here -- this claim is about
# source shape, not behavior a probe would otherwise have to execute.
# Paths are matched RELATIVE TO $SEARCH_ROOT (via `cd` first) -- this
# suite's own claims live under a directory literally named .../fansearch/,
# so matching against the absolute path would false-negative every trap
# fixture exercising this exact probe.
OFFENDERS="$(cd "$SEARCH_ROOT" && grep -rl "fansearch_proxy\|PROXY_ADAPTERS" . --include="*.py" 2>/dev/null \
  | grep -v "^\./adapters/proxy/" \
  | grep -v "^\./cli/commands/fansearch\.py$" \
  | grep -v "^\./cli/commands/drill\.py$" \
  | grep -v "^\./fansearch/" \
  | grep -v "^\./core/config\.py$" \
  || true)"
if [ -n "$OFFENDERS" ]; then
  echo "RED: the core engine references the fansearch seam outside its own files: $OFFENDERS"
  exit 1
fi

python3 - "$ROOT" <<'PYEOF'
import sys
from pathlib import Path

root = sys.argv[1]
sys.path.insert(0, root)

from recurvelib.core.config import load
import tempfile

# A recurve.toml with no [fansearch] table at all must default to "off" --
# not just documented, actually parsed that way.
with tempfile.TemporaryDirectory() as tmp:
    toml_path = Path(tmp) / "recurve.toml"
    toml_path.write_text(
        '[project]\nname = "ablation-check"\n\n[target]\ntree = "."\n\n'
        '[suites.x]\ndir = ".recurve/claims/x"\n'
    )
    (Path(tmp) / ".recurve" / "claims" / "x").mkdir(parents=True)
    cfg = load(toml_path)
    if cfg.fansearch_proxy != "off":
        print(f"RED: a recurve.toml with no [fansearch] table resolved to "
              f"fansearch_proxy={cfg.fansearch_proxy!r}, expected 'off'")
        sys.exit(1)

# emit_for_matrix's discovery lookup must be silently empty (zero overhead,
# zero receipt change) for any project that has never run a campaign.
from recurvelib.io.receipts import discovery_provenance
from types import SimpleNamespace
with tempfile.TemporaryDirectory() as tmp2:
    fake_cfg = SimpleNamespace(state_dir=Path(tmp2))
    result = discovery_provenance(fake_cfg)
    if result != {}:
        print(f"RED: discovery_provenance found data with no promotions.jsonl present: {result}")
        sys.exit(1)

print("GREEN: fansearch_proxy defaults to off; the core engine has zero references to the "
      "fansearch seam outside its own files; discovery_provenance is silently empty by default")
sys.exit(0)
PYEOF
