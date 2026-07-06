"""A cheap, untrusted scorer for the dyadic shell-model weighted-energy
functional Phi_gamma(u) = sum_n lam^(2*gamma*n) * u_n^2 (lam = 2), truncated
at index N.

`dphi_dt` computes the time derivative of that functional along the shell
ODE via the closed-form telescoping identity: the transport terms of
adjacent shells cancel except at the two boundaries (n = 0, pinned to zero,
and n = N, the truncation), leaving a dissipation term, an interior flux
term, and a boundary flux term. `score` grades how confidently a state
satisfies the target monotonicity inequality (dphi_dt <= 0), for use as a
cheap ranking signal -- never as a substitute for a real proof.
"""

LAM = 2.0


def dphi_dt(nu, alpha, gamma, N, u):
    dissipation = -2 * nu * sum(
        LAM ** (2 * (alpha + gamma) * n) * u[n] ** 2 for n in range(N + 1)
    )
    interior_flux = 2 * (LAM ** (2 * gamma + 1) - LAM) * sum(
        LAM ** ((1 + 2 * gamma) * n) * u[n] ** 2 * u[n + 1] for n in range(N)
    )
    boundary_flux = -2 * LAM ** ((1 + 2 * gamma) * N + 1) * u[N] ** 2 * u[N + 1]
    return dissipation + interior_flux + boundary_flux


def score(nu, alpha, gamma, N, u):
    return 1.0 if dphi_dt(nu, alpha, gamma, N, u) <= 1e-9 else 0.0
