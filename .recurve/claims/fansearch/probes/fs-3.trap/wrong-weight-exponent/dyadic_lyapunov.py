"""KNOWN-BAD fixture: the shell RHS drops the factor of 2 from the
dissipation exponent -- a plausible transcription slip that silently
changes the identity."""
from __future__ import annotations

from dataclasses import dataclass

LAM = 2.0


@dataclass(frozen=True)
class Candidate:
    N: int
    b: tuple
    d: tuple

    def __post_init__(self):
        if len(self.b) != self.N + 1:
            raise ValueError(f"b must have length N+1={self.N + 1}, got {len(self.b)}")
        if len(self.d) != self.N:
            raise ValueError(f"d must have length N={self.N}, got {len(self.d)}")


def _shell_rhs(nu, alpha, u, n, N):
    um1 = u[n - 1] if n - 1 >= 0 else 0.0
    up1 = u[n + 1] if n + 1 <= N else 0.0
    return -(nu * LAM ** (alpha * n) * u[n]) + LAM ** n * um1 ** 2 - LAM ** (n + 1) * (u[n] * up1)


def dphi_dt(nu, alpha, candidate, u):
    N = candidate.N
    total = 0.0
    for n in range(N + 1):
        total += candidate.b[n] * 2 * u[n] * _shell_rhs(nu, alpha, u, n, N)
    for n in range(N):
        total += candidate.d[n] * (
            _shell_rhs(nu, alpha, u, n, N) * u[n + 1] + u[n] * _shell_rhs(nu, alpha, u, n + 1, N)
        )
    return total
