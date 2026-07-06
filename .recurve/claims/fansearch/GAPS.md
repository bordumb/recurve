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

## FS-4 — compile_to_claim's output elaborates through the real gate ✓

`recurvelib/adapters/proxy/compile_to_claim.py` automates F0 Stage 3's
hand-authored bridge: `compile_to_claim(candidate)` specializes
`shell_single_active_dissipative` (`SH7`, the sibling `navier_stokes`
repo) to a candidate's concrete weights, returning a named theorem, a
check-file pin referencing it, and a trap redefining it as an impostor —
never writing to disk or invoking the gate itself (a campaign engine would
do that). This validates the *mechanism*, not new mathematics: any single
candidate's single-shell dissipativity is already a proven corollary of
`SH7`; a genuinely novel multi-shell bound is a harder, still-open
question a survivor's numbers alone do not hand you a proof of. Verified
against the real sibling toolchain (`lake env lean`): the compiled
theorem elaborates kernel-clean, and the compiled trap is rejected with a
type mismatch, on a concrete `N=3` candidate. Negative space (kept RED as
a counterexample): `probes/fs-4.trap/wrong-rhs-index/` asserts the
dissipation coefficient at index `0` instead of `N` — a plausible
off-by-one — and the sibling gate's own type-checker rejects it.

The sibling repo's default checkout does not have `SH7` merged onto its
main branch yet (it landed on a matched feature branch there); the probe
walks up to find a sibling `navier_stokes/` and SKIPs (non-blocking,
`oracle_waiver` declared) when `SH7` is not present there — the AB-12/TK-2
pattern. `$NAVIER_STOKES_REPO` overrides the lookup for a real run.

## FS-5 — drill --fansearch measures a proxy's own discriminative power ✓

`recurve drill --fansearch` is F6's second tooth: for every registered
`ProxyEvaluator` besides `off`, it looks for `DRILL_KNOWN_GOOD`/
`DRILL_KNOWN_BAD`/`DRILL_THRESHOLD` on the adapter's own module and
measures false-negative/false-positive rate, failing the drill on any
leak — the same spirit as `--fuzz`/`--iso`'s generated-variant regression
checks, adapted to a scorer rather than a probe. `dyadic_lyapunov`'s
fixture: two known-good candidates (one of them the plain, unweighted
energy — Cheskidov's own unconditional dissipation result, not just an
empirical anchor) and three known-bad ones (flat or steeply-varying
weights paired with large positive cross terms, which the earlier
symbolic check already showed pump energy upward). This is a narrower
adaptation of the PRD's own "known-bad candidates from the archive's
`refuted_by_trap` set": there is no archive here (F2 is descoped for this
domain, §2), so the fixture is a fixed, hand-verified set rather than one
mined from a live campaign's rejects — the discriminative-power regression
guard is real either way. Negative space (kept RED as a counterexample):
`probes/fs-5.trap/threshold-collapsed/` sets `DRILL_THRESHOLD = 0.0`, at
which every known-bad candidate trivially "passes" — caught as 3/3 false
positives.

## FS-6 — the campaign engine: archive everything, stop on a measure ✓

`recurvelib/fansearch/campaign.py::run_campaign` is the engine F2-F4
descoped down to: propose a candidate (classical optimization, F0 Stage 2),
score it, archive it — every round, not just survivors — and halt on
either a wall-clock budget or `dry_generations` consecutive rounds with no
new record. Both thresholds are config, not a raw loop-iteration count
picked out of the air; this is the same "reuse the controller" discipline
the burndown loop's own `max_consecutive_failures`/`runaway_net_positive_
cycles` halts already use, applied to a different counter (no new
gate-confirmed candidate, rather than no ledger progress). A new record
above the promotion threshold gets checked against the real target repo
(read-only, a scratch temp file — nothing is written there) before it
counts as gate-confirmed; without a target repo the campaign still runs
and archives, it just cannot confirm anything. Negative space (kept RED as
a counterexample): `probes/fs-6.trap/off-by-one-stop/` loosens the
dry-generations comparison by one — caught immediately (3 rounds run
where exactly 2 were configured).

`recurvelib/fansearch/promote.py::promote_candidate` is the one step here
that mutates another repo's history for good: it appends the compiled
theorem to the target source, writes a check/trap/probe triple matching
that repo's own convention, rebuilds, and baselines there — never
automatic, always one explicit call naming one archived candidate. This
was verified against the real sibling repo, not just read: a real
campaign round found a record-scoring `N=4` candidate, `promote_candidate`
wrote it in as `SHX1`, and the sibling's own gate closed it green (0
regressions, 42/42 traps still RED) — the same mechanism FS-4 checks in
isolation, exercised here as part of a full round-trip.

## FS-7 — a discovered claim's receipt says so ✓

An optional `discovery` field (`domain`, `proxy_score`) on the receipt
schema, populated by `make_receipt` and attached by `emit_for_matrix` only
when a gap id appears in `<state_dir>/fansearch/promotions.jsonl` — a
hand-authored claim's receipt carries neither key. Included in
`self_sha256` (known at receipt-creation time, unlike `signer_fields`,
which is excluded because it arrives after the hash is fixed). Verified
against the real sibling repo's own gate run (using this worktree's own
`recurve`, since the field does not exist on whatever is checked out on
its default branch yet): `SHX1`'s receipt carries `{"domain":
"dyadic_lyapunov", "proxy_score": 1.0}`; `SH7`'s, promoted by hand, carries
neither key; the chain still verifies end to end. Negative space (kept RED
as a counterexample): `probes/fs-7.trap/leaks-to-all/` falls back to a
placeholder `discovery` object for every gap instead of `None` — caught
immediately (a hand-authored gap acquiring a fabricated discovery field).

## FS-8 — a second domain: counterexample hunting, sharing zero domain code ✓

`recurvelib/adapters/proxy/counterexample.py` grades a candidate initial
datum by how strongly it refutes "a large weighted norm forces blowup":
numerically integrate the truncated shell ODE (RK4, its own
reimplementation of the shell system — not an import of
`dyadic_lyapunov`'s) forward from the datum, and compare the worst
weighted norm reached against its starting value. A datum with a large
starting norm whose trajectory stays comparably sized is a genuine
refutation; one with too small a norm to matter, or one whose norm
actually grows without bound, is not. This is the mathematical shape
behind the sibling `navier_stokes` repo's `FR-SH4Q`/
`sh4_dissipative_blowup_refuted`, generalized to the extent that matters
for F5: a second domain plugs into the same `ProxyEvaluator`/registry
seam with no changes anywhere else.

Two things worth recording plainly rather than glossing over:

- **Numerical stability, not just correctness.** A fixed step count
  reports spurious "blowup" at high shell indices from ordinary
  floating-point round-off amplified by the system's own (real, not
  buggy) upward-transport term — the same mechanism that makes multi-
  shell states genuinely non-dissipative. The step count now scales with
  the fastest linear rate and the integration horizon; verified against
  the *exact* analytic solution for a single-active-shell state (pure
  linear decay once transport vanishes) to a relative error of `~1.7e-10`,
  not just "looks stable."
- **`compile_to_claim` was not attempted for this domain.** Unlike
  `dyadic_lyapunov`'s single-shell dissipativity — a clean, one-shot
  algebraic identity that generalizes to *any* weight (`SH7`) — `FR-SH4Q`'s
  refutation is a specific instance built from several composed lemmas
  (`dyadic_shell_upper_bound`, an envelope/summability argument, an
  Archimedean shell-index choice). A fresh instance at different
  parameters is plausibly reachable by reusing that machinery, but it is
  real per-instance Lean proof engineering, not a mechanical
  specialization — attempting it without the time to verify it properly
  would risk exactly the kind of "looks done" claim this whole tool
  exists to prevent. The domain adapter (`building_blocks`,
  `ProxyEvaluator`) is complete and gate-verified; the promotion half is
  open work, honestly left open.

Negative space (kept RED as a counterexample):
`probes/fs-8.trap/wrong-dissipation-exponent/` drops a factor of 2 from
the dissipation exponent — the probe's comparison against the exact
analytic solution catches the resulting mismatch, RED.
