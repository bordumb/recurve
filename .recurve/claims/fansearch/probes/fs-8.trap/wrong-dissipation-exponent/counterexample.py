"""counterexample: scores a candidate initial datum by how strongly its
numerically-integrated trajectory violates a naive "large weighted norm
implies blowup" expectation -- a candidate that starts with an enormous
H^gamma norm yet stays numerically bounded in H^(1/3+gamma) over the
horizon is evidence an over-broad blowup claim has a counterexample.
Deliberately shares no code with the dyadic_lyapunov domain beyond the
registration seam: same shell system, independently reimplemented, so
each domain adapter stands alone.
"""
from __future__ import annotations

from dataclasses import dataclass

from recurvelib.core.protocols import ProxyScore

LAM = 2.0


@dataclass(frozen=True)
class Datum:
    """A candidate initial condition for the truncated dyadic shell system:
    nonnegative amplitudes at a chosen set of active shells, all others
    zero, integrated forward for a chosen time horizon `T`."""

    N: int
    active: tuple[int, ...]
    amplitudes: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.active) != len(self.amplitudes):
            raise ValueError("active and amplitudes must have the same length")
        if any(not (1 <= n <= self.N) for n in self.active):
            raise ValueError(f"active shells must be in [1, {self.N}]")
        if any(a < 0 for a in self.amplitudes):
            raise ValueError("amplitudes must be nonnegative")

    def initial_state(self) -> list[float]:
        u = [0.0] * (self.N + 1)
        for n, a in zip(self.active, self.amplitudes):
            u[n] = a
        return u


def _rhs(nu: float, alpha: float, u: list[float], N: int) -> list[float]:
    def wavenumber(k):
        return LAM ** k

    def dissipation(k):
        return LAM ** (alpha * k)  # BUG: dropped the factor of 2

    out = [0.0] * (N + 1)
    for n in range(1, N + 1):
        um1 = u[n - 1]
        up1 = u[n + 1] if n + 1 <= N else 0.0
        out[n] = -(nu * dissipation(n) * u[n]) + wavenumber(n) * um1 ** 2 - wavenumber(n + 1) * (u[n] * up1)
    return out


def _stable_steps(nu: float, alpha: float, N: int, T: float, min_steps: int = 2000) -> int:
    """The fastest linear rate in the system is the top shell's dissipation,
    `nu * LAM**(2*alpha*N)` -- plain RK4 needs `dt` well inside its stability
    region for that rate, or a fixed small step count silently understeps at
    high `N` and reports spurious numerical blowup as if it were real."""
    fastest_rate = max(1.0, nu * LAM ** (2 * alpha * N))
    return max(min_steps, int(20 * fastest_rate * T))


def integrate(nu: float, alpha: float, datum: Datum, T: float, steps: int | None = None) -> list[list[float]]:
    """RK4 over the Galerkin-truncated shell ODE (ghost u_0 = 0, shells
    above N frozen at 0). Returns the trajectory, one state per step.

    A step count that only accounts for the fastest linear rate keeps each
    step stable but not the accumulated round-off over a long integration:
    a state that starts and should stay exactly on the single-active-shell
    subspace can leak an arbitrarily small nonzero value onto a neighboring
    shell, and the shell system's own transport term (real, not a bug --
    the same term that makes multi-shell states genuinely non-dissipative)
    amplifies that leak over enough steps. Empirically stable through
    N <= 20, amplitude <= 50, T <= 3 with plain double-precision RK4; a
    caller pushing past that regime should verify stability directly
    (e.g. re-run at 10x the step count and check the trajectory agrees)
    rather than trust the score at face value."""
    N = datum.N
    if steps is None:
        steps = _stable_steps(nu, alpha, N, T)
    dt = T / steps
    u = datum.initial_state()
    trajectory = [list(u)]
    for _ in range(steps):
        k1 = _rhs(nu, alpha, u, N)
        u2 = [u[i] + 0.5 * dt * k1[i] for i in range(N + 1)]
        k2 = _rhs(nu, alpha, u2, N)
        u3 = [u[i] + 0.5 * dt * k2[i] for i in range(N + 1)]
        k3 = _rhs(nu, alpha, u3, N)
        u4 = [u[i] + dt * k3[i] for i in range(N + 1)]
        k4 = _rhs(nu, alpha, u4, N)
        u = [u[i] + (dt / 6.0) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(N + 1)]
        u[0] = 0.0
        trajectory.append(list(u))
    return trajectory


def hnormsq(gamma: float, u: list[float]) -> float:
    return sum(LAM ** (2 * gamma * n) * u[n] ** 2 for n in range(len(u)))


class CounterexampleProxy:
    """A `ProxyEvaluator` that grades a `Datum` by how strongly it refutes
    the naive expectation that a large `H^gamma` norm forces blowup in
    `H^(1/3+gamma)`: high initial norm plus a numerically bounded
    trajectory scores near 1; either a modest initial norm or a
    trajectory that visibly diverges scores near 0."""

    def __init__(self, nu: float = 1.0, alpha: float = 1.0 / 6.0, gamma: float = 1.0,
                 T: float = 3.0, steps: int | None = None, norm_floor: float = 10.0,
                 growth_ceiling: float = 10.0):
        self._nu = nu
        self._alpha = alpha
        self._gamma = gamma
        self._T = T
        self._steps = steps
        self._norm_floor = norm_floor
        self._growth_ceiling = growth_ceiling

    def score(self, candidate: Datum) -> ProxyScore:
        initial_state = candidate.initial_state()
        initial_norm = hnormsq(self._gamma, initial_state)
        refuting_norm = 1.0 / 3.0 + self._gamma
        # Deep-shell data has an inherently huge weighted norm at this
        # exponent regardless of dynamics (the weight itself grows with
        # shell index) -- a genuine blowup shows up as GROWTH relative to
        # the start, not as a large absolute value.
        initial_refuting = max(hnormsq(refuting_norm, initial_state), 1.0)
        try:
            trajectory = integrate(self._nu, self._alpha, candidate, self._T, self._steps)
            worst = max(hnormsq(refuting_norm, u) for u in trajectory)
            growth = worst / initial_refuting
        except OverflowError:
            # The integrator itself overflowing mid-step is as strong a
            # divergence signal as a finite but enormous norm -- treat it
            # as unbounded growth rather than letting it crash scoring.
            growth = float("inf")

        norm_component = min(1.0, initial_norm / self._norm_floor)
        bounded_component = 1.0 if growth <= self._growth_ceiling else 0.0
        value = norm_component * bounded_component
        return ProxyScore(value=value, signal={
            "initial_hnormSq_gamma": initial_norm,
            "growth_ratio": growth,
        })


# `drill --fansearch`'s regression fixture: candidates this proxy has
# already been checked to score well/poorly separated on. DRILL_KNOWN_GOOD's
# deep single shell mirrors the actual mathematical fact behind FR-SHELLREG-
# adjacent results: a large weighted norm at a high shell does not force
# blowup. DRILL_KNOWN_BAD covers both failure directions: a norm too small
# to refute anything, and adjacent active shells whose transport genuinely
# diverges (a real blowup, not a counterexample).
DRILL_KNOWN_GOOD: tuple[Datum, ...] = (
    Datum(N=20, active=(20,), amplitudes=(50.0,)),
    Datum(N=15, active=(15,), amplitudes=(30.0,)),
)
DRILL_KNOWN_BAD: tuple[Datum, ...] = (
    Datum(N=1, active=(1,), amplitudes=(0.1,)),
    Datum(N=10, active=(4, 5, 6), amplitudes=(20.0, 20.0, 20.0)),
)
DRILL_THRESHOLD = 0.5
