#!/bin/bash
# FS-3: the dyadic_lyapunov proxy -- registered, deterministic, and correct
# against the same closed-form identity FS-1's sanity check verified.
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
sys.modules[spec.name] = mod  # dataclasses' ClassVar/InitVar lookup needs this registered
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: candidate module failed to import: {e}")
    sys.exit(1)

LAM = 2.0


def expected_dphi_dt(nu, alpha, gamma, N, u):
    term1 = -2 * nu * sum(LAM ** (2 * (alpha + gamma) * n) * u[n] ** 2 for n in range(N + 1))
    term2 = 2 * (LAM ** (2 * gamma + 1) - LAM) * sum(
        LAM ** ((1 + 2 * gamma) * n) * u[n] ** 2 * u[n + 1] for n in range(N)
    )
    term3 = -2 * LAM ** ((1 + 2 * gamma) * N + 1) * u[N] ** 2 * u[N + 1]
    return term1 + term2 + term3


# Same 7 vectors FS-1 independently verified, recast as (nu, alpha, gamma, N, u)
# with a pure geometric candidate b_n = LAM^(2*gamma*n), d = 0.
VECTORS = [
    (1.0, 0.5, 0.5, 3, [0.0, 0.0, 0.0, 5.0, 0.0, 0.0]),
    (0.3, 1.0, 0.2, 6, [0.0] * 6 + [2.0] + [0.0] * 2),
    (0.0, 0.7, 0.9, 1, [0.0, 10.0, 0.0, 0.0]),
    (1.0, 1.0, 1.0, 0, [0.0, 0.0, 0.0]),
    (2.0, 0.2, 0.3, 10, [0.0] * 10 + [1.0] + [0.0] * 2),
    (0.01, 0.5, 1.0, 3, [0.0, 3.0, 4.0, 0.0, 0.0, 0.0]),
    (0.001, 0.3, 1.5, 4, [0.0, 0.0, 2.0, 3.0, 0.0, 0.0, 0.0]),
]

TOL = 1e-6
for nu, alpha, gamma, N, u in VECTORS:
    b = tuple(LAM ** (2 * gamma * n) for n in range(N + 1))
    d = tuple(0.0 for _ in range(N))
    candidate = mod.Candidate(N=N, b=b, d=d)
    got = mod.dphi_dt(nu, alpha, candidate, list(u[: N + 2]))
    want = expected_dphi_dt(nu, alpha, gamma, N, u)
    rel = abs(got - want) / max(1.0, abs(want))
    if rel > TOL:
        print(f"RED: N={N} gamma={gamma}: expected dphi_dt={want!r}, got {got!r}")
        sys.exit(1)

# malformed candidate (wrong-length b) is refused, not silently truncated/padded
try:
    mod.Candidate(N=3, b=(1.0, 2.0), d=(0.0, 0.0, 0.0))
    print("RED: a wrong-length b was accepted instead of raising")
    sys.exit(1)
except ValueError:
    pass

# registered, resolvable, and produces a valid ProxyScore
try:
    from recurvelib.adapters.proxy import PROXY_ADAPTERS
    from recurvelib.adapters.registry import resolve
    from recurvelib.core.protocols import ProxyScore
except ImportError as e:
    print(f"RED: seam not wired: {e}")
    sys.exit(1)

cls = resolve("dyadic_lyapunov", PROXY_ADAPTERS, "proxy")
proxy1, proxy2 = cls(), cls()
cand = mod.Candidate(N=6, b=tuple(2.0 ** n for n in range(7)), d=tuple(0.0 for _ in range(6)))
s1, s2 = proxy1.score(cand), proxy2.score(cand)
if not isinstance(s1, ProxyScore) or not (0.0 <= s1.value <= 1.0):
    print(f"RED: score is not a valid ProxyScore: {s1!r}")
    sys.exit(1)
if s1.value != s2.value:
    print(f"RED: not deterministic across fresh instances: {s1.value} != {s2.value}")
    sys.exit(1)

print("GREEN: dphi_dt matches the verified closed form on 7 vectors; malformed candidates "
      "refused; registered and deterministic")
sys.exit(0)
PYEOF
