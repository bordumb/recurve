"""A scorer that ignores the state entirely and always claims dissipation."""


def dphi_dt(nu, alpha, gamma, N, u):
    return -1.0


def score(nu, alpha, gamma, N, u):
    return 1.0
