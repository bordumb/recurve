# PRD — fansearch proxy provenance: make the Stage-0 proxy evolution auditable

> Scope: a provenance/auditability gap in `fansearch`'s **F0 gate** (the
> cheap-first proxy-validation stages, `fansearch.md` §F0). Today the proxy —
> the *gameable, untrusted guide* half of fansearch — is iterated as
> **throwaway sympy/numpy/scipy scripts** before any `recurvelib` code is
> touched. That throwaway step is deliberate and correct for speed. The bug is
> that we throw away the *reasoning trail*, and that trail is load-bearing:
> each proxy iteration typically *finds and fixes a real defect* that would
> otherwise feed the gate false candidates. This plan makes the proxy's
> evolution and its ground-truth validation a first-class, checked-in artifact,
> without touching the referee surface.

> **Written pre-launch.** No deployments to preserve. This is purely additive
> provenance; it changes nothing about what the gate believes.

## 0 · The problem, stated

fansearch's safety story (`fansearch.md` §6) is a *separation of trust*: the
proxy is a gameable guide, the kernel-checked `matrix --gate` is the sole
arbiter. A candidate is a **conjecture** until the gate confirms it. That story
has a silent hole on the **proxy side**:

- **A proxy is only worth searching on once it recognizes ground truth** (F0
  Stage 0: feed it a known-good and known-bad object; if it can't separate
  them, fix the proxy first). Building a proxy that passes that gate is
  *iterative* — and each iteration is substantive work, not scaffolding.
- **We discard that work.** The scripts live in a scratch dir and evaporate.
  What survives is, at best, a single number ("the proxy says no blow-up in the
  window") with **no record of why that proxy should be believed** — which
  ground-truth failures were caught, which artifacts were fixed, what the final
  validation battery returned.

The result is a provenance asymmetry: recurve's *confirmed* claims are
rigorously auditable (a probe, a trap that must stay RED, a dated `observed`,
`#print axioms`), but the *discovery* side that feeds them has none of this for
its most trust-critical component. A drifting or subtly-wrong proxy is exactly
the "a guard blessing its own counterexample" failure mode the gate exists to
prevent — one level up, on the generator.

## 1 · Worked example that motivated this (navier_stokes, Front B / SH6)

Attacking the dyadic wall SH6's blow-up side (a `dyadic_blowup`-style search for
an initial datum that blows up at some α ∈ [1/3, 1/2)) began, per protocol, with
the F0 Stage-0 ground-truth gate. It took **four proxy iterations** to get a
trustworthy blow-up detector, each catching a real defect:

| ver | proxy | defect it exposed | ground-truth verdict |
|----|-------|-------------------|----------------------|
| v1 | shipped fixed-step RK4 (`counterexample.py`) | **stiffness** — fabricated blow-up at α=0.6 where SH5 *proves* regularity | FAILS ground truth |
| v2 | stiff solver (`scipy` Radau/BDF) | removed the false positives; but couldn't confirm it *fires* on true blow-up | partial |
| v3 | + N-refinement | a finite truncation is globally regular — true dyadic blow-up is an ∞-cascade phenomenon; needs an N→∞ signature | separated inviscid (diverges) vs SH5 (saturates) |
| v4 | cascade-front certificate (penetration depth + A(k) decay slope) | the weighted-norm metric was **weight-confounded** (λ^{(8/3)n} inflates any cascade-to-top); front metrics are weight-independent | PASSES ground truth |

Only v4 recognizes both ground truths (inviscid → Kolmogorov λ^{-k/3} cascade to
shell N; SH5 α≥1/2 → front stalls at injection). The eventual finding — *no
blow-up datum in the window for the tested profiles; the cascade stalls* — is
**only trustworthy because of v1→v4**. Handed just v4's output, a reviewer
cannot see that the two most natural proxies (v1, v3-metric) would have lied.
Yet under today's workflow, v1–v3 are `/tmp` files that vanish, and the audit
trail that *earns* v4's credibility is gone.

## 2 · Why this belongs in recurve (not just in the consuming repo)

recurve already ships the seed of the mechanism:

- `DRILL_KNOWN_GOOD` / `DRILL_KNOWN_BAD` + `DRILL_THRESHOLD` on each proxy
  (`recurvelib/adapters/proxy/*.py`) — the ground-truth battery.
- `recurve drill --fansearch` — audits the proxy against that battery.

What's missing is **persistence and history**: `drill` is a point-in-time check;
it records neither the verdict over time nor the *iterations* that produced a
passing proxy. The proxy's `DRILL_KNOWN_*` fixtures are the *answer key*, but the
*worked solutions* (why the current integrator/metric, what earlier ones got
wrong) are uncaptured.

## 3 · Proposal

Three layers, cheapest first (mirroring the F0 philosophy):

1. **Proxy-evolution artifacts are versioned and in-repo, never scratch.**
   Each proxy for a domain keeps its iteration history + a changelog entry per
   version ("what defect this fixed, what ground-truth case exposed it").
   **Placement convention — a new first-class location:** in a consuming repo
   this lives under **`.recurve/fansearch/<campaign>/`**, a sibling of
   `.recurve/claims/`, `.recurve/state/`, `.recurve/workflows/`. Deliberately
   **not** under `.recurve/claims/` and **not** in `docs/`: `claims/` is the
   gate-**confirmed** ledger, the proxy is the **untrusted generator**, and
   keeping those two trust classes in separate namespaces is the same separation
   §6 of `fansearch.md` rests on (it also keeps the "never edit `.recurve/claims/`
   to pass the gate" boundary unambiguous, and a proxy may feed several suites so
   it should not be buried under one). This mirrors recurve's own layout, where
   `recurvelib/adapters/proxy/` is separate from any claim. Done here:
   `navier_stokes/.recurve/fansearch/frontB_stage0/`. For a `recurvelib` proxy
   (a registered, reusable domain), the adapter itself still lives beside its
   peers in `recurvelib/adapters/proxy/`.

2. **A persisted F0 "proxy validation record"** — the proxy analogue of a
   claim's dated `observed`, stored in `.recurve/fansearch/<campaign>/`. A
   checked-in, dated artifact recording: the ground-truth battery (the
   `DRILL_KNOWN_*` objects), the metric/integrator used, and the pass/fail
   verdict, with a one-line provenance note per proxy version. Extend `recurve
   drill --fansearch` with `--record` to append this (append-idempotent, like
   `record append`), so a proxy's trustworthiness is reconstructable and its
   drift is detectable across runs.

3. **`recurve fansearch` surfaces the history.** `fansearch status` / a new
   `fansearch proxy log <domain>` shows the validation-record timeline: which
   proxy version is live, when it last passed drill, and the changelog. A
   candidate promoted via `fansearch promote` should carry, in its RED-first
   claim's provenance, *which proxy version + validation record* scored it —
   closing the loop so a confirmed discovery names the guide that found it.

4. **Deterministic campaign↔claim linking — the join key is the claim `id`.**
   Prose references ("this attacks SH6") are not joinable; a data scientist
   analyzing/optimizing the system needs a machine join. Every campaign dir
   carries a `manifest.yaml` **junction table** with *typed edges* to claims —
   `links.targets[]` (attacked), `links.calibrated_by[]` (ground truth),
   `links.produced[]` (promoted) — each an `{id, suite}` pair, plus an
   `artifacts[]` list joining every script file to the campaign. Each artifact
   file also repeats the keys in its own header, so a file is joinable in
   isolation. This is **normalized**: the manifest is the single source of truth
   for the edges; claims are *not* back-annotated (the gap schema would allow it —
   `additionalProperties: true` — but denormalizing invites drift). A
   referential-integrity check (prototype `.recurve/fansearch/check_links.py`,
   future `recurve fansearch validate`) fails if any FK is dangling or mis-routed
   or any listed artifact is missing — so the link is *verified*, not asserted.
   The whole campaign↔claim graph is then a deterministic
   `JOIN manifest.links.*.id = gaps.yaml.id`.

## 4 · Non-goals

- **Does not** make the proxy trusted or change the arbiter. The gate remains
  the sole confirmer; this only makes the *guide's* pedigree auditable.
- **Does not** touch the referee surface, `matrix --gate`, or any claim/probe/
  trap semantics.
- **Does not** require keeping every dead script forever — a changelog entry +
  the final passing proxy + the ground-truth record is the minimum; full
  iteration source is kept when (as in §1) the dead versions encode a
  *why-not* that a future searcher needs.

## 5 · Acceptance

- A fansearch domain's F0 Stage-0 outcome is reconstructable months later from
  checked-in artifacts alone: which ground-truth objects, which verdict, which
  proxy version, and the changelog of what earlier versions got wrong.
- `recurve drill --fansearch --record` writes/append-updates a dated validation
  record; `fansearch proxy log` reads it back.
- A promoted candidate's claim provenance names the proxy version that scored
  it. Removing/altering that record is a detectable drift, not a silent one.
- Every campaign's `manifest.yaml` passes referential integrity: each claim FK
  (`targets`/`calibrated_by`/`produced`) resolves to a real ledger `id` in its
  declared suite, and every listed artifact file exists. The campaign↔claim
  relationship is a deterministic JOIN, not prose — verifiable by
  `.recurve/fansearch/check_links.py` (→ `recurve fansearch validate`).
