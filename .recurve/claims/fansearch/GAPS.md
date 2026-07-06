# fansearch — discovery proxy validation

> Precondition claims for the fan-out discovery search described in
> `docs/plans/fansearch.md`. Before any engine code lands, these establish
> that a cheap, untrusted evaluator can genuinely recognize known-good
> mathematical structure and reject known-bad structure in the target
> shell-model domain (the sibling `navier_stokes` repo). Throwaway
> validation code, not shipped engine code — the real engine's registered
> protocol lands as later claims once this holds.

## Conventions

`missing-surface` claims about a throwaway sanity harness, `reads: none` —
each probe runs the harness for real (no caching, no self-reported results)
and independently recomputes the expected numbers from the closed-form
identity it is checking the harness against.

## FS-1 — the proxy sanity check recognizes real dissipative structure ✓

A cheap scorer for the shell-model weighted-energy functional (the quantity
behind the sibling `navier_stokes` repo's `FR-SHELLREG` result) computes the
functional's time derivative via the closed-form telescoping identity
(dissipation term + interior flux + boundary flux) and grades a state by
whether that derivative is non-positive. On states in the regime the
functional is proven dissipative for, it reports satisfaction; on states
known analytically to violate the inequality (adjacent active shells whose
transport dominates a small viscosity), it reports violation. Negative
space (kept RED as a counterexample): a scorer that ignores the sampled
state entirely, or one whose derivative computation uses the wrong
exponent, turns the probe RED.
