#!/bin/bash
# FS-8: the counterexample domain -- a second ProxyEvaluator sharing zero
# domain code with dyadic_lyapunov beyond the registration seam. Its
# numerical integrator is checked against the exact analytic solution for
# a single-active-shell state (a pure linear decay once transport terms
# vanish), and its proxy correctly separates a real refuting candidate
# from a too-small one and from one that genuinely diverges.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  IMPL="$TRAP_FIXTURE/counterexample.py"
else
  IMPL="$ROOT/recurvelib/adapters/proxy/counterexample.py"
fi

python3 - "$ROOT" "$IMPL" <<'PYEOF'
import importlib.util
import math
import sys

root, impl_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

spec = importlib.util.spec_from_file_location("counterexample_candidate", impl_path)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(f"RED: counterexample module failed to import: {e}")
    sys.exit(1)

LAM = 2.0

# --- malformed candidates refused, not silently accepted -------------------
for kwargs, label in [
    (dict(N=3, active=(1, 2), amplitudes=(1.0,)), "mismatched active/amplitudes length"),
    (dict(N=3, active=(4,), amplitudes=(1.0,)), "active shell above N"),
    (dict(N=3, active=(1,), amplitudes=(-1.0,)), "negative amplitude"),
]:
    try:
        mod.Datum(**kwargs)
        print(f"RED: a malformed Datum ({label}) was accepted instead of raising")
        sys.exit(1)
    except ValueError:
        pass

# --- the integrator matches the exact analytic single-shell solution -------
nu, alpha, N, amp, T = 1.0, 1.0 / 6.0, 8, 5.0, 2.0
rate = nu * LAM ** (2 * alpha * N)
datum = mod.Datum(N=N, active=(N,), amplitudes=(amp,))
trajectory = mod.integrate(nu, alpha, datum, T, steps=None)
numeric = trajectory[-1][N]
analytic = amp * math.exp(-rate * T)
rel_err = abs(numeric - analytic) / analytic
if rel_err > 1e-6:
    print(f"RED: integrator disagrees with the exact analytic decay: "
          f"numeric={numeric!r} analytic={analytic!r} rel_err={rel_err!r}")
    sys.exit(1)

# --- the proxy separates: refuting / too-small / genuinely-diverging -------
proxy = mod.CounterexampleProxy(nu=1.0, alpha=1.0 / 6.0, gamma=1.0)
refuting = mod.Datum(N=20, active=(20,), amplitudes=(50.0,))
too_small = mod.Datum(N=1, active=(1,), amplitudes=(0.1,))
diverges = mod.Datum(N=10, active=(4, 5, 6), amplitudes=(20.0, 20.0, 20.0))

s_refuting = proxy.score(refuting).value
s_small = proxy.score(too_small).value
s_diverges = proxy.score(diverges).value

if s_refuting < 0.5:
    print(f"RED: a genuine refuting candidate scored low: {s_refuting}")
    sys.exit(1)
if s_small >= 0.5:
    print(f"RED: a too-small-to-matter candidate scored high: {s_small}")
    sys.exit(1)
if s_diverges >= 0.5:
    print(f"RED: a genuinely-diverging candidate scored high: {s_diverges}")
    sys.exit(1)

print(f"GREEN: malformed candidates refused; integrator matches analytic decay "
      f"(rel_err={rel_err:.2e}); proxy separates refuting={s_refuting:.3f} "
      f"small={s_small:.3f} diverges={s_diverges:.3f}")
sys.exit(0)
PYEOF
