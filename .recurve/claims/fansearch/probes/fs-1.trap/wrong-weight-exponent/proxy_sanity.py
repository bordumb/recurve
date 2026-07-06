"""A scorer that drops the factor of 2 from the weighting exponent -- a
plausible transcription slip that silently changes the identity."""

LAM = 2.0


def dphi_dt(nu, alpha, gamma, N, u):
    term1 = -2 * nu * sum(LAM ** ((alpha + gamma) * n) * u[n] ** 2 for n in range(N + 1))
    term2 = 2 * (LAM ** (gamma + 1) - LAM) * sum(
        LAM ** ((0.5 + gamma) * n) * u[n] ** 2 * u[n + 1] for n in range(N)
    )
    term3 = -2 * LAM ** ((0.5 + gamma) * N + 1) * u[N] ** 2 * u[N + 1]
    return term1 + term2 + term3


def score(nu, alpha, gamma, N, u):
    return 1.0 if dphi_dt(nu, alpha, gamma, N, u) <= 1e-9 else 0.0
