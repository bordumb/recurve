"""dyadic_lyapunov: scores a weighted-energy-style shell functional by how
often it satisfies the target dissipation inequality (dPhi/dt <= 0) across
a fixed battery of single- and multi-active-shell states. Cheap (direct
sums, no solver), deterministic (a fixed battery, not resampled per call),
and untrusted -- a real claim's proof is the only thing that decides.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from recurvelib.core.protocols import ProxyScore

LAM = 2.0


@dataclass(frozen=True)
class Candidate:
    """`sum_{n=0}^N b_n u_n^2 + sum_{n=0}^{N-1} d_n u_n u_{n+1}` over the
    truncated dyadic shell system (mirrors, does not import, the
    Lean-proven shell ODE in the sibling navier_stokes repo)."""

    N: int
    b: tuple[float, ...]
    d: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.b) != self.N + 1:
            raise ValueError(f"b must have length N+1={self.N + 1}, got {len(self.b)}")
        if len(self.d) != self.N:
            raise ValueError(f"d must have length N={self.N}, got {len(self.d)}")


def _shell_rhs(nu: float, alpha: float, u: list[float], n: int, N: int) -> float:
    um1 = u[n - 1] if n - 1 >= 0 else 0.0
    up1 = u[n + 1] if n + 1 <= N else 0.0
    return (-(nu * LAM ** (2 * alpha * n) * u[n])
            + LAM ** n * um1 ** 2
            - LAM ** (n + 1) * (u[n] * up1))


def dphi_dt(nu: float, alpha: float, candidate: Candidate, u: list[float]) -> float:
    """The candidate functional's time derivative along the shell ODE,
    summed directly (not the single-shell closed form) so it is valid for
    any state, not only ones supported at a single shell."""
    N = candidate.N
    total = 0.0
    for n in range(N + 1):
        total += candidate.b[n] * 2 * u[n] * _shell_rhs(nu, alpha, u, n, N)
    for n in range(N):
        total += candidate.d[n] * (
            _shell_rhs(nu, alpha, u, n, N) * u[n + 1]
            + u[n] * _shell_rhs(nu, alpha, u, n + 1, N)
        )
    return total


def _make_battery(N: int, seed: int, n_states: int) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    battery = []
    for i in range(n_states):
        u = [0.0] * (N + 1)
        if i < n_states // 4:
            idx = rng.randint(1, N)
            u[idx] = rng.uniform(0.5, 10.0)
        else:
            k = rng.randint(2, min(4, N))
            for idx in rng.sample(range(1, N + 1), k):
                u[idx] = rng.uniform(0.1, 10.0)
        battery.append(tuple(u))
    return tuple(battery)


class DyadicLyapunovProxy:
    """`ProxyEvaluator` for the dyadic_lyapunov domain (docs/plans/fansearch.md
    F5). `nu`/`alpha` are the shell system's own physical parameters, fixed
    per proxy instance (not part of the candidate) -- a campaign varies the
    candidate's weights, not the physical regime. The battery is generated
    once per truncation level `N` from a fixed seed, then reused: pure and
    deterministic given a candidate, as the port requires."""

    def __init__(self, nu: float = 1.0, alpha: float = 0.5,
                 n_states: int = 60, seed: int = 20260706):
        self._nu = nu
        self._alpha = alpha
        self._seed = seed
        self._n_states = n_states
        self._batteries: dict[int, tuple[tuple[float, ...], ...]] = {}

    def _battery_for(self, N: int) -> tuple[tuple[float, ...], ...]:
        if N not in self._batteries:
            self._batteries[N] = _make_battery(N, self._seed, self._n_states)
        return self._batteries[N]

    def score(self, candidate: Candidate) -> ProxyScore:
        battery = self._battery_for(candidate.N)
        values = [dphi_dt(self._nu, self._alpha, candidate, list(u)) for u in battery]
        hits = sum(1 for v in values if v <= 1e-9)
        return ProxyScore(value=hits / len(values), signal={"worst_violation": max(values)})
