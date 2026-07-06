#!/bin/bash
# Runs a candidate proxy scorer against a fixed table of shell-model states
# and checks it against an independently-computed closed-form derivative.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  IMPL="$TRAP_FIXTURE/proxy_sanity.py"
else
  IMPL="$HERE/fs-1_impl/proxy_sanity.py"
fi

if [ ! -f "$IMPL" ]; then
  echo "RED: $IMPL not found"
  exit 1
fi

python3 - "$IMPL" <<'PYEOF'
import importlib.util
import sys

impl_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("proxy_sanity_candidate", impl_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

LAM = 2.0


def expected_dphi_dt(nu, alpha, gamma, N, u):
    # The telescoped weighted-energy derivative identity, lam = 2, for a
    # sequence u (indices 0..N+1) with u[0] = 0.
    term1 = -2 * nu * sum(LAM ** (2 * (alpha + gamma) * n) * u[n] ** 2 for n in range(N + 1))
    term2 = 2 * (LAM ** (2 * gamma + 1) - LAM) * sum(
        LAM ** ((1 + 2 * gamma) * n) * u[n] ** 2 * u[n + 1] for n in range(N)
    )
    term3 = -2 * LAM ** ((1 + 2 * gamma) * N + 1) * u[N] ** 2 * u[N + 1]
    return term1 + term2 + term3


# (label, is_dissipative_regime, nu, alpha, gamma, N, u)
VECTORS = [
    ("single-shell-a", True, 1.0, 0.5, 0.5, 3, [0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
    ("single-shell-b", True, 0.3, 1.0, 0.2, 6, [0.0] * 6 + [2.0] + [0.0] * 2),
    ("single-shell-zero-visc", True, 0.0, 0.7, 0.9, 1, [0.0, 10.0, 0.0, 0.0]),
    ("all-zero", True, 1.0, 1.0, 1.0, 0, [0.0, 0.0, 0.0]),
    ("single-shell-high-n", True, 2.0, 0.2, 0.3, 10, [0.0] * 10 + [1.0] + [0.0] * 2),
    ("adjacent-shells-transport", False, 0.01, 0.5, 1.0, 3, [0.0, 3.0, 4.0, 0.0, 0.0, 0.0]),
    ("adjacent-shells-steep-gamma", False, 0.001, 0.3, 1.5, 4, [0.0, 0.0, 2.0, 3.0, 0.0, 0.0, 0.0]),
]

TOL = 1e-6
PASSING_THRESHOLD = 0.95

value_errors = []
dissipative_scores = []
violating_scores = []

for label, dissipative, nu, alpha, gamma, N, u in VECTORS:
    want = expected_dphi_dt(nu, alpha, gamma, N, u)
    got = mod.dphi_dt(nu, alpha, gamma, N, list(u))
    rel = abs(got - want) / max(1.0, abs(want))
    if rel > TOL:
        value_errors.append(f"{label}: expected dphi_dt={want!r}, got {got!r}")

    s = mod.score(nu, alpha, gamma, N, list(u))
    (dissipative_scores if dissipative else violating_scores).append(s)

if value_errors:
    print("RED: candidate dphi_dt disagrees with the closed-form identity:")
    for e in value_errors:
        print("  -", e)
    sys.exit(1)

avg_dissipative = sum(dissipative_scores) / len(dissipative_scores)
max_violating = max(violating_scores)

if avg_dissipative < PASSING_THRESHOLD:
    print(f"RED: proxy rejects known-good dissipative states (avg score {avg_dissipative:.3f} "
          f"< {PASSING_THRESHOLD})")
    sys.exit(1)

if max_violating >= PASSING_THRESHOLD:
    print(f"RED: proxy accepts a known-violating state (score {max_violating:.3f} "
          f">= {PASSING_THRESHOLD})")
    sys.exit(1)

print(f"GREEN: dphi_dt matches the closed-form identity on {len(VECTORS)} vectors; "
      f"dissipative avg score {avg_dissipative:.3f}, worst violating score {max_violating:.3f}")
sys.exit(0)
PYEOF
