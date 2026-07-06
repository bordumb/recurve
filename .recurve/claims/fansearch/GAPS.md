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

## FS-1 — the proxy sanity check recognizes real dissipative structure

A cheap scorer for the shell-model weighted-energy functional (the quantity
behind the sibling `navier_stokes` repo's `FR-SHELLREG` result) must, when
handed states in the regime that functional is proven dissipative for,
report that they satisfy the target monotonicity inequality — and must,
when handed states that are known analytically to violate it (adjacent
active shells whose transport dominates a small viscosity), report that
they do not. A scorer that always reports "satisfies" regardless of the
state, or one that recomputes the derivative with an incorrect weighting
exponent, passes neither test. Negative space (kept RED as a counterexample):
a scorer that ignores the sampled state entirely, or one whose derivative
computation uses the wrong exponent, turns the probe RED.
