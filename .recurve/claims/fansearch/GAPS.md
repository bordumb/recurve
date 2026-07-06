# fansearch — discovery proxy validation and engine

> Claims for the fan-out discovery search described in
> `docs/plans/fansearch.md`. FS-1 establishes, with throwaway validation
> code, that a cheap evaluator can genuinely recognize known-good
> mathematical structure and reject known-bad structure in the target
> shell-model domain (the sibling `navier_stokes` repo). FS-2 onward are the
> real, shipped engine that validation earns: the `ProxyEvaluator` port and
> its registration seam, with domain adapters and the rest of the engine
> landing as later claims.

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

## Further validation before any engine code — three throwaway checks

Not ledger claims (throwaway scripts, per this suite's own precondition
rule) — recorded here so the next claim's author does not repeat the work.

**Is there real signal in the candidate grammar?** Random/grid sampling
over a richer candidate family (diagonal shell weights of several shapes —
geometric, polynomial, monotone-random — plus optional cross-term
coefficients) against a battery of single- and multi-active-shell states
shows real separation: mean score 0.696, stdev 0.176, range 0.18–1.00
across 400 sampled candidates, against a pure-geometric reference scoring
0.69–0.78 depending on its rate. Not a flat landscape, and naive random
sampling already reaches the reference's range. Worth searching.

**Does classical optimization already solve it?** `scipy.optimize.
differential_evolution` over the same parametrization (proxy score as
objective) robustly recovers/beats the geometric reference: 0.965–1.000
across 5 independent seeds, all with zero violations on the DE's own
training battery, versus the reference's 0.69–0.75. Per this PRD's own
decision rule, that descopes the engine: a classical optimizer stands in
for the LLM fan-out/breeding machinery (islands, `Proposer`,
`campaign_runner`) for this domain, unless a later check shows an LLM adds
value a plain optimizer can't reach. Checked analytically (symbolic sum
expansion, not just numerically): no choice of diagonal weight or
cross-term coefficient makes the functional's derivative non-positive for
*every* nonnegative multi-shell state short of the already-known constant-
weight case — so the near-perfect DE scores are a genuine but non-universal
empirical fit, not a hidden new theorem. Exactly the behavior the proxy/gate
split is designed for: a good score guides, it does not decide.

**Does candidate → statement → kernel-check work smoothly by hand?**
Yes. A hand-authored generalization of the weighted-energy derivative
identity — dissipativity of a single active shell holds for *any*
nonnegative diagonal weight and *any* cross-term coefficients, not just
the geometric one — went RED → GREEN through the real gate in the sibling
`navier_stokes` repo (recorded there as `SH7`, `NavierStokes/Shells/
Basic.lean`), kernel-clean, no regressions. The bridge works.

## FS-2 — the ProxyEvaluator port resolves through the generalized registry ✓

`ProxyEvaluator`/`ProxyScore` (`recurvelib/core/protocols.py`) are the
first pluggable port outside the confirmation loop's own `Actor`/`World`
spine. Registration goes through a new generic `build_registry`/`resolve`
pair in `recurvelib/adapters/registry.py` — not a fourth hand-copy of the
adversary/governor/boundary shape, per this PRD's own instruction; the
existing three may migrate onto it separately. `recurvelib/adapters/proxy/`
holds the registry (`PROXY_ADAPTERS`) and a trivial `off` scorer (a fixed
neutral score, so the seam is real before any domain adapter exists).
`[fansearch] proxy = "off"` (default) is the config knob; an unrecognized
value is refused at config load. Negative space (kept RED as a
counterexample): `probes/fs-2.trap/fourth-hand-copy/` reintroduces
`resolve_proxy`/`build_proxy_registry` as their own hand-copied functions —
the probe's source-shape check catches it, RED.

## FS-3 — the dyadic_lyapunov proxy is registered, deterministic, and correct ✓

`recurvelib/adapters/proxy/dyadic_lyapunov.py` generalizes the throwaway
Stage 0–2 scripts into a real, registered `ProxyEvaluator`: `Candidate`
(a diagonal weight sequence `b` plus cross-term coefficients `d` over a
truncation level `N`), and `dphi_dt` — the functional's derivative summed
directly from the shell RHS, valid for *any* state (not only the
single-shell case `SH7` covers in closed form). `DyadicLyapunovProxy`
scores a candidate by the fraction of a fixed, seeded battery of
single- and multi-active-shell states it stays non-positive on — pure and
deterministic given a candidate, per the port's own requirement.
`[fansearch] proxy = "dyadic_lyapunov"` is now a valid config value.
Negative space (kept RED as a counterexample): `probes/fs-3.trap/
wrong-weight-exponent/` drops a factor of 2 from the dissipation exponent —
the probe's comparison against the same closed form `FS-1` verified
catches the resulting mismatch, RED.
