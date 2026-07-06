#!/bin/bash
# FS-5: F6's anti-reward-hack teeth -- `recurve drill --fansearch` measures
# each registered ProxyEvaluator's known-good/known-bad separation and
# fails the drill on a regression.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  IMPL="$TRAP_FIXTURE/dyadic_lyapunov.py"
else
  IMPL="$ROOT/recurvelib/adapters/proxy/dyadic_lyapunov.py"
fi

python3 - "$ROOT" "$IMPL" <<'PYEOF'
import importlib.util
import sys

root, impl_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

spec = importlib.util.spec_from_file_location("dyadic_lyapunov_candidate", impl_path)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: candidate module failed to import: {e}")
    sys.exit(1)

good, bad, threshold = mod.DRILL_KNOWN_GOOD, mod.DRILL_KNOWN_BAD, mod.DRILL_THRESHOLD
if not good or not bad:
    print("RED: DRILL_KNOWN_GOOD/DRILL_KNOWN_BAD fixture is empty")
    sys.exit(1)

proxy = mod.DyadicLyapunovProxy()
fn = sum(1 for c in good if proxy.score(c).value < threshold)
fp = sum(1 for c in bad if proxy.score(c).value >= threshold)
if fn or fp:
    print(f"RED: known-good/known-bad separation regressed (fn={fn}/{len(good)}, "
          f"fp={fp}/{len(bad)})")
    sys.exit(1)

print(f"GREEN: proxy correctly separates {len(good)} known-good and {len(bad)} known-bad "
      f"candidates at threshold {threshold}")
sys.exit(0)
PYEOF
# `recurve drill --fansearch` itself is not re-invoked here: it acquires its
# own tree lock, which would deadlock/conflict with the lock this probe's own
# caller (baseline/matrix --gate) already holds. The check above exercises
# the exact same logic cmd_drill's --fansearch branch runs.
