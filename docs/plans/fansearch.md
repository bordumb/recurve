# PRD — fansearch: fan-out discovery search with the gate as confirmer

> Scope: a new `recurvelib` subsystem, `fansearch`, plus a `recurve
> fansearch` CLI surface. Today recurve **confirms** claims it is handed
> (authored by a human or a PRD, then burned down under
> `matrix --gate`). It cannot **discover** them. fansearch adds the missing
> half: a fan-out generate-and-select loop that mines the uncovered
> frontier for candidate claims, ranks them with a *cheap, untrusted proxy
> evaluator*, and promotes only the survivors into RED-first claims that the
> existing gate then confirms. The name is an homage to DeepMind's
> **FunSearch** — literally "fan out to search" — with one deliberate
> improvement: FunSearch trusts its evaluator as the sole arbiter; fansearch
> treats the proxy as a gameable *guide* and keeps recurve's kernel-checked
> gate as the arbiter. In any domain where a trusted verifier exists
> (formalized math, but also SAT/ILP feasibility, executable specs),
> that separation is exactly what makes evolutionary LLM search *safe to
> believe*.

> **Written pre-launch.** No deployments to preserve. Where a cleaner design
> wants a breaking change to an internal protocol, take it. Nothing here
> touches the referee surface — that is the whole point (§6).

## 0 · This completes an intention the codebase already states

Three mechanisms recurve already has, aimed at a target it has never fired at:

1. **The Actor *proposes*.** `recurvelib/loop/runtime.py` already declares
   the actor as "a pluggable coding agent: given the contract, one item,
   and failing evidence, it returns a diff" (`Actor.propose(contract,
   item, evidence)`). Today it proposes *fixes to an authored claim*. Its
   protocol shape doesn't fit discovery unchanged (no contract/item exists
   yet, and the output is a diff, not a candidate construction — see F3),
   but its *spirit* — a pluggable, untrusted generator behind a protocol —
   is exactly the shape a proposer needs. fansearch introduces a sibling
   protocol (`Proposer`, F3), not a forced reuse of `Actor` itself.
2. **The trap/probe discipline *confirms any proposer*.** The capture rule
   (`recurvelib/loop/runtime.py::capture(trap_red_on_wrong,
   trap_green_on_real)` — a candidate's trap is accepted only if it
   discriminates: RED on the wrong implementation, GREEN on the real one)
   already doesn't care who authored the candidate — human, PRD, or search
   loop. It is already a *proposer-agnostic* acceptance rule inside a
   *proposer-agnostic* confirmer (the gate: `matrix --gate`, the trap/probe
   machinery broadly).
3. **The frontier *surfaces the unclaimed*.** `recurve frontier`
   (`recurvelib/analysis/frontier.py::compute_frontier`, fed by
   `analysis/surface.py`'s raw surface extraction) already "surfaces the
   ranked uncovered ids — what no claim covers." That is a search space
   with no searcher pointed at it.

fansearch is the **proposer-at-scale** that turns (3), the uncovered
frontier, into candidate claims via a sibling of (1), a new `Proposer`
protocol shaped like the Actor's but fit for discovery, made *safe* by
(2), the same proposer-agnostic gate. We are not importing FunSearch as a
foreign pattern; we are pointing existing recurve mechanisms — and one
new, small, honestly-new one — at the discovery target they were shaped
for.

## 1 · The shape — the FunSearch triangle, with recurve's confirmer

FunSearch needs three things; recurve already owns the hardest one.

| FunSearch component | fansearch realization |
|---|---|
| **Search space** (programs/constructions to evolve) | a domain-supplied *grammar of candidates* (F5): weighted functionals, counterexample data, self-similar profiles, heuristics… |
| **Cheap automatic evaluator** (scores every candidate) | a *proxy evaluator* (F1): milliseconds, graded 0..1, **untrusted** — it guides, it does not decide |
| **(FunSearch stops here — its evaluator is the arbiter)** | **the gate** (`matrix --gate`, capture rule, kernel/exec check): expensive, binary, **ungameable** — the arbiter |

**The one invariant fansearch adds to recurve:** *the proxy ranks; the gate
decides.* A candidate's proxy score never promotes it, closes it, or earns
it a place in the ledger. It only earns it a place in the **queue** to be
authored RED-first and put to the gate. This is the same discipline recurve
already enforces for the Actor ("believe the gate, not yourself") — fansearch
just makes it structural, because the proxy is *designed to be optimized
against* and therefore *designed to be gamed*.

Why this beats vanilla FunSearch where a verifier exists: FunSearch's results
are only as trustworthy as its evaluator, and its evaluator is the very
surface the search optimizes — so spurious/overfit "discoveries" are a known
failure mode. fansearch's discoveries are kernel-checked. A construction that
merely fools the cheap proxy dies at promotion (its trap stays GREEN, or its
statement pin fails to elaborate, or `#print axioms` shows `sorryAx`). The
proxy can be as loose and fast as we like precisely *because* it is not
trusted.

## 2 · Requirements

### F0 · POC validation gate — prove the domain before building the engine

Not a requirement of the shipped system — a precondition on starting F1.
None of F1–F8's build cost (a new protocol, islands, an archive, a fan-out
engine, breeding, a `drill` extension, receipts wiring) is justified until
the `dyadic_lyapunov` domain is shown to have real, exploitable structure
and the promotion bridge is shown to actually work. Four stages, cheapest
and most falsifiable first — each one **strictly cheaper than the thing it
de-risks**, each with a clear stop condition. No `recurvelib` code, no
`Proposer`, no fan-out infra, no islands — throwaway scripts only, until
Stage 3.

- **Stage 0 — proxy sanity check (minutes, one function call).** Feed the
  `ProxyEvaluator` the *already-proven* functional behind `FR-SHELLREG`
  (the hand-built weighted-energy quantity, via
  `weighted_energy_sum_deriv_identity_boundary`). Confirm it scores as
  satisfying the target inequality. **Stop condition:** if the proxy can't
  recognize known-good ground truth, its symbolic/numeric derivative
  computation is wrong — fix that before anything else, since every later
  stage assumes the proxy itself is trustworthy *as a guide*.

  ```python
  # throwaway, not shipped code -- sanity-checks the proxy against ground truth
  known_good = weighted_energy_functional()   # the FR-SHELLREG functional, as data
  score = proxy.score(known_good)
  assert score.value >= PASSING_THRESHOLD, "proxy rejects a proven-correct functional"
  ```

- **Stage 1 — is there any signal? (seconds–minutes, sympy + numpy, no LLM).**
  Random/grid-sample a few hundred candidates from `building_blocks` (shell
  weights, cross terms, exponents), score all of them with the proxy.
  Check: does the score distribution show real separation (a landscape
  worth searching), or is it flat/uninformative — and does naive random
  sampling ever get close to the known baseline. **Stop condition:** a
  flat landscape, or nothing within striking distance of the baseline,
  means the `building_blocks` parametrization (or the target inequality
  itself) needs rethinking before any generation loop is built around it.

- **Stage 2 — does classical optimization already solve it? (still no
  LLM).** Run a plain optimizer (`scipy.optimize.differential_evolution`,
  or CMA-ES) over the same parametrization, proxy as the objective. **This
  is the load-bearing check for F3/F4's scope, not just a sanity check:**
  if numerical optimization alone recovers or beats the known baseline,
  the LLM fan-out/breeding engine (F3/F4 — the most expensive part of this
  PRD to build) is not earning its keep for *this* domain. That outcome
  should **descope** the POC to proxy-guides/gate-decides (F1, F5, F6)
  plus a classical optimizer standing in for F3/F4 entirely — not a reason
  to build islands and fan-out anyway. LLM-driven generation only earns
  its cost where the search space has *compositional* structure a
  parameter optimizer can't reach (new qualitative building-block
  combinations, not just weight tuning) — Stage 4 is where that gets
  tested, and only if it's still an open question after Stage 2.

- **Stage 3 — does the promotion bridge actually work? (one hand-authored
  claim, the real gate).** Take whatever Stage 1/2 found most promising,
  hand-write (or one Claude Code call) the `compile_to_claim` output for
  it — a real pinned Lean statement + trap + probe — and run it through
  the actual gate (`recurve baseline`, `matrix --gate`). One claim, not a
  campaign; the real repo/toolchain, but nothing else from F1–F8. **Stop
  condition:** if candidate→Lean-statement→kernel-check doesn't work
  smoothly by hand for a real, non-trivial functional, that is the actual
  bottleneck — better to find and fix it here than to discover it only
  after a campaign engine exists to feed it.

- **Stage 4 — does an LLM add anything over optimization? (a handful of
  Claude calls, still no fan-out infra).** Only reached if Stage 2 left it
  open. Prompt Claude a few times with the same `building_blocks`, score
  the results with the proxy, and compare against Stage 2's optimizer
  output. This is the actual crux of whether F3/F4 is worth building at
  all — not an assumption the PRD should carry in unexamined.

### F1 · The `ProxyEvaluator` port — cheap, graded, untrusted

A protocol in `recurvelib/core` (sibling to the existing `Actor`/`World`
protocols), with domain implementations under
`recurvelib/adapters/fansearch/<domain>/`:

```python
class ProxyEvaluator(Protocol):
    def score(self, candidate: Candidate) -> ProxyScore: ...
    # ProxyScore: value in [0,1] (higher = more promising) PLUS a
    # structured `signal` (e.g. worst-case violation magnitude, SOS
    # residual, numerical blow-up indicator) used for breeding, not ranking
    # alone. MUST be cheap (target < 100ms) and MUST be pure/deterministic
    # given the candidate + a fixed sample seed.
```

Hard constraints: the proxy (a) never writes to the tree, (b) never invokes
the gate, (c) is registered and swappable exactly like the adversary
adapters (`[fansearch] proxy = dyadic_lyapunov | counterexample | …` in
`recurve.toml`), and (d) is itself **auditable by `drill`** — F6.

**Do not copy `recurvelib/adapters/registry.py`'s existing shape a fourth
time.** That file already has three near-identical pairs —
`build_adversary_registry`/`resolve_adversary`,
`build_governor_registry`/`resolve_governor`,
`build_boundary_registry`/`resolve_boundary` — each hand-duplicated with
only the protocol/method name changed. Adding `build_proxy_registry`/
`resolve_proxy` the same way would be the fourth copy of one function.
Generalize instead, and this PRD is the excuse to do it:

```python
# recurvelib/adapters/registry.py — one generic pair, not four copies
def build_registry(entries: dict[str, type], protocol: type,
                   methods: tuple[str, ...]) -> dict[str, type]:
    for name, cls in entries.items():
        _require_methods(cls, protocol, methods)
    return dict(entries)


def resolve(name: str, registry: dict[str, type], kind: str) -> type:
    if name not in registry:
        raise UnknownAdapterError(f"unknown {kind} {name!r}; known: {', '.join(sorted(registry))}")
    return registry[name]
```

`ADVERSARY_ADAPTERS = build_registry(entries, Adversary, ("review",))` and
`PROXY_ADAPTERS = build_registry(entries, ProxyEvaluator, ("score",))`
become one-line call sites instead of one-function-each. The existing
three axes can migrate opportunistically (separate, low-risk cleanup
commit); fansearch's own registration must not add a fourth hand-copy
regardless of whether that migration happens first.

### F2 · Population & archive — islands, not a leaderboard

Reuse FunSearch's islands to avoid premature convergence. `recurvelib/`
`fansearch/population.py`:

- **Islands**: K parallel populations; a candidate lives on one island; the
  best-scoring exemplars are periodically sampled *within* an island for
  breeding, and islands are reset/reseeded from the global best on a schedule
  (the standard FunSearch anti-collapse move).
- **Archive**: every candidate ever scored, with its `ProxyScore`, lineage
  (parent exemplars, generation, island), and *gate outcome once known*
  (`untested | RED_authored | GREEN_confirmed | refuted_by_trap`). The
  archive is the campaign's memory and the seed for the next campaign — the
  fansearch analogue of the ledger.
- Diversity is measured on a domain-supplied *descriptor* (F5) so the archive
  can keep behaviorally-distinct candidates, not just high-scoring near-dupes.

### F3 · Fan-out generation — a `Proposer` port, new fan-out infrastructure

**Correction to an earlier draft of this section:** "reuse the loop's agent
fan-out" overclaimed. `recurvelib.loop.runtime.run(world, actor,
admission_report, contract, max_cycles)` is a *sequential*, single-actor
loop — there is no parallel fan-out inside `recurvelib` to import. "One
fresh agent per cycle" is an *orchestration-layer* pattern (`recurve run
--agent 'claude -p …'`, spawned repeatedly by a skill/shell driver, e.g.
`/recurve-work`'s endless mode) — a convention, not a library function.
fansearch's fan-out (M proposers *concurrently*, not one cycle at a time)
is genuinely **new infrastructure**: a small, contained
`recurvelib/fansearch/campaign_runner.py` that spawns M proposer
invocations per generation (thread pool or subprocess pool — same shape
`eval/`'s own `core/runner.py` already uses for concurrent cells) and
collects their `Candidate`s before scoring.

**Also correct: proposers are not `Actor`s.** `Actor.propose(contract,
item, evidence) -> diff` assumes a pre-existing authored claim (`contract`,
`item`) to fix — exactly backwards for discovery, which runs *before* any
claim exists, and it returns a `diff` (a file patch), not a `Candidate` (a
structured, domain-defined value). Forcing fansearch's proposers through
the literal `Actor` protocol either breaks that protocol's own type
contract or silently overloads one interface with two incompatible
behaviors — the opposite of what a protocol/port is for. The honest
design is a **sibling port**, structurally inspired by `Actor` (same
spirit: a pluggable thing whose output is untrusted until confirmed
downstream) but its own type, in `recurvelib/core` next to `Actor`/`World`:

```python
class Proposer(Protocol):
    def propose(self, building_blocks, exemplars: list[Candidate]) -> Candidate: ...
    # No contract/item/evidence -- there is no authored claim yet.
    # `exemplars`: high-scoring candidates from this proposer's own island
    # (F2), for best-shot prompting. Returns a Candidate, never a diff --
    # compile_to_claim (F5) is the ONLY place a Candidate becomes a diff-
    # shaped artifact (a claim's statement/trap/probe files).
```

Each proposer is handed: the domain's building blocks (F5), a sample of
high-scoring exemplars from its island (F2), and the explicit instruction
to *propose a new candidate construction*, not to prove anything.
Proposers write nothing to the referee surface — same boundary discipline
`Actor`s already observe, enforced the same way (§6), just via a distinct
protocol rather than a strained reuse of `Actor`'s.

### F4 · Selection & breeding

Score every new candidate with the proxy (F1), place it on its island (F2),
and drive the next generation from the islands' exemplars. Breeding is
LLM-mediated (mutate/combine exemplars, guided by the `signal`), not a fixed
genetic operator — this is FunSearch, not a GA. Selection pressure is on the
proxy score; **diversity pressure** is on the descriptor (F2) so the loop
does not collapse onto one motif.

### F5 · The domain adapter — the only domain-specific code

A domain plugs in via one adapter (`recurvelib/adapters/fansearch/<domain>/`)
supplying exactly:

1. **`building_blocks`** — the candidate grammar / primitives the proposers
   compose (for dyadic: shell weights, cross terms, exponents, data motifs;
   for a counterexample auditor: data families, amplitudes, base times).
2. **`ProxyEvaluator`** (F1).
3. **`descriptor`** — a cheap behavioral fingerprint for diversity (F2).
4. **`compile_to_claim(candidate) -> ClaimDraft`** — the promotion bridge
   (F5→F6): how a survivor becomes a *pinned statement + trap + probe*,
   i.e. a RED-first claim in the target repo's ledger. This is the crux:
   fansearch's output is not a number, it is an **authored claim** the
   normal gate can burn down. Same purity discipline as `ProxyEvaluator`
   (F1): `compile_to_claim` is a pure function of `candidate` — it returns
   a `ClaimDraft` value (statement/trap/probe text), it does not itself
   write files, touch the tree, or invoke the gate. Writing the draft to
   disk and running `recurve baseline` on it is the campaign engine's job
   (domain-agnostic, F6), not the adapter's — the same
   compute/write separation this whole design already applies to
   `ProxyEvaluator`.

Everything else — islands, fan-out, budget, provenance — is domain-agnostic
engine.

### F6 · Anti-reward-hack — the proxy is untrusted, the gate is not

This is the requirement that makes fansearch *recurve* rather than *just
FunSearch*. Three teeth:

- **Promotion is RED-first, always.** `compile_to_claim` must emit a claim
  with a trap the probe rejects and a statement pin that fails on a mangled
  target — the same authoring discipline every hand-written claim obeys.
  A candidate that only fools the proxy produces a claim whose **trap stays
  GREEN** or whose **probe never goes RED-first** — caught mechanically at
  `recurve baseline`, before any credit is given.
- **`drill` audits the proxy.** Extend the existing sabotage audit: `drill
  --fuzz` already measures probe false-positives; add a fansearch mode that
  feeds the proxy known-bad candidates (from the archive's `refuted_by_trap`
  set) and asserts the proxy's *ranking* did not systematically prefer them
  — i.e. measure and bound the proxy's false-positive rate as a *search
  guide*. A proxy that ranks garbage highly is a bad guide, not a security
  hole (the gate still catches the garbage), but drilling it keeps the search
  efficient and honest.
- **No proxy score enters the ledger.** The ledger records only gate-measured
  truth (`observed` quotes real dated gate output, never a prediction — the
  existing rule). A promoted claim's `receipts` (F7) *may* record the proxy
  score as provenance, but the claim's status is decided solely by the gate.

### F7 · Provenance & receipts — a projection of the archive, not a second store

A receipt is **derived from** the archive entry it corresponds to, at the
moment a candidate is promoted — never populated independently. Concretely:
`emit_for_matrix` (existing, unchanged) already writes one receipt per
verdict; fansearch's only addition is that a promoted claim's receipt
carries extra fields *read straight out of that candidate's own archive
entry* (F2) — campaign id, generation, island, parent exemplars, proxy
score at promotion — plus the gate outcome the receipt already records.
`recurve receipts` can then answer "was this claim discovered by search,
and what guided it?"; `recurve stats` reports search yield (candidates
generated : claims authored : claims gate-confirmed) as a first-class rate.

The failure mode this avoids: if the archive and the receipt each recorded
their own copy of "lineage," they could silently diverge (a bug in one
writer, not the other). One fact, one writer, one reader — the archive is
the source, the receipt is a read of it at promotion time.

### F8 · Budget & stopping — reuse the controller

A campaign is bounded like a burndown run: a token/wall-clock budget and a
**dry-generations** stop (the controller's existing "K cycles with no new
confirmed progress" halt, applied to *gate-confirmed survivors*, not proxy
score — a campaign that keeps raising its proxy ceiling while producing zero
gate-confirmed claims is *diverging*, and must halt, not celebrate). Reuse
`recurve decide`/`sense` to make the halt a measured decision, not a vibe.

## 3 · CLI surface

```
recurve fansearch run --domain <name> [--generations N] [--islands K]
                      [--fanout M] [--budget …] [--seed-from <campaign>]
    # run a campaign: fan-out → proxy-score → breed → promote survivors
    # to RED-first claims, then STOP (does not itself close them — the
    # normal `recurve run` burns the promoted queue down under the gate).

recurve fansearch status        # islands, best scores, archive, promoted queue
recurve fansearch archive       # list/inspect candidates + lineage + gate outcome
recurve fansearch promote <id>  # manually push one archived candidate to a claim
recurve fansearch drill         # F6 audit: proxy false-positive rate vs known-bad
```

Note the seam: `fansearch run` *discovers and authors*; the existing `recurve
run`/`cycle`/`matrix --gate` *confirms and closes*. fansearch never closes a
claim — it only fills the RED backlog the burndown loop already knows how to
drain. This keeps the discovery layer and the confirmation layer cleanly
separable (and independently ablatable, §6).

## 4 · Fit with the existing loop

fansearch is an **upstream mode** of the improvement loop, not a replacement:

```
                 ┌─────────────── fansearch (NEW: discovery) ───────────────┐
frontier ──────► │ fan-out proposers → proxy rank → islands → promote       │
(uncovered ids)  └───────────────────────────┬──────────────────────────────┘
                                              ▼  (RED-first claims authored)
                 ┌──────────── recurve run / cycle (EXISTING: confirmation) ─┐
                 │ recurve next → sculpt → matrix --gate → promote open→closed│
                 └───────────────────────────────────────────────────────────┘
```

`recurve next` continues to pick from *authored* claims; fansearch is what
*produces* authored claims when the human/PRD backlog is exhausted but the
frontier is not. A natural cadence: burn down the authored backlog; when
`recurve next` reports "no open work" but `recurve frontier` still shows
uncovered ids, run a fansearch campaign to refill the backlog, then burn down
again.

## 5 · First adapters (POC → second domain)

### POC — `dyadic_lyapunov` (the cleanest evaluator/search-space fit)

Grounded in the `navier_stokes` shell suite, which already has the machinery:

- **building_blocks**: shell weights `b_n`, cross terms `u_n u_{n+1}`,
  exponents, over the explicit ODE `shellRHS`.
- **ProxyEvaluator**: for a candidate functional `Φ = ∑ b_n g(u_n, …)`,
  compute `dΦ/dt` symbolically (it is a computable polynomial in the `u_n` —
  the suite already proved the derivative-identity lemmas
  `weighted_energy_sum_deriv_identity_boundary` &c.) and score by *sampled
  violation* of the target inequality (`dΦ/dt ≤ 0`, or a Riccati
  `dΦ/dt ≥ c Φ^{3/2}`) over random nonnegative states — plus an optional SOS
  residual for a sharper signal. Milliseconds; graded; untrusted.
- **descriptor**: the weight decay rate / support / which inequality it
  targets.
- **compile_to_claim**: emit a Lean claim pinning the differential inequality
  for the candidate functional (statement pin `:= <name>` + impostor trap +
  probe), RED-first. The gate then decides. A hit is a *new monotone
  quantity / Riccati functional* — the kind of object that pushed
  `FR-SHELLREG` (single-shell regularity below the SH5 wall) through by hand;
  the search targets extending the data class or sharpening the critical
  constant.

### Second — `counterexample` (generalize FR-SH4Q into a capability)

- **building_blocks**: data families (single/multi-shell), amplitudes, base
  times, parameter points.
- **ProxyEvaluator**: numerically integrate the model from the candidate
  datum and score how strongly it *violates* a target theorem's conclusion
  (e.g. "stays bounded where the pin claims blow-up"). Cheap.
- **compile_to_claim**: emit the *refutation* claim (`¬ <over-broad
  statement>`), RED-first, gate-confirmed — exactly the shape of the
  hand-built `sh4_dissipative_blowup_refuted`. The capability: an **automated
  over-claim auditor** for formalized libraries — point it at a suite of
  pinned theorems and let it hunt statement-scope errors, each one a
  kernel-checked refutation.

These two share zero domain code beyond their adapters — the point of F5.

## 6 · Guardrails (recap — the reason this is safe to run unattended)

- **The proxy cannot corrupt the ledger** — it never writes, never gates,
  never sets status. Worst case: a *bad guide* wastes generation budget,
  bounded by F8's dry-generations halt.
- **Promotion is RED-first** — a fooled proxy yields a claim that fails its
  own trap/pin at `baseline`, before credit (F6).
- **The write boundary and lock still hold** — `Proposer`s observe the same
  boundary discipline `Actor`s do (F3); a campaign acquires the tree lock
  like any run.
- **Ablatable** — `[fansearch] proxy = off` reduces the loop to hand-authored
  claims (today's behavior); this belongs in the ablation matrix
  (`eval-full.md`) as a new switch: *does discovery search beat
  human/PRD authoring at refilling the backlog, at equal gate discipline?*

## 7 · Build order

0. **F0 — the POC validation gate.** Throwaway scripts only; no
   `recurvelib` code. Does not complete until Stage 3 (a real,
   hand-authored claim clears the actual gate) has passed. **A Stage 2
   result showing classical optimization already recovers/beats the known
   baseline changes everything downstream:** step 2 below shrinks to
   "F1 + F5 + F6, optimizer standing in for F3/F4" — the islands/fan-out
   engine is *not* built by default in that case, only if Stage 4
   subsequently shows an LLM adds real value classical search doesn't.
1. **F1 + F5-skeleton** — the `ProxyEvaluator` protocol, registered through
   the generalized `build_registry`/`resolve` (not a fourth hand-copy of
   `adapters/registry.py`'s existing pattern); a trivial `off`/identity
   proxy so the seam exists before any real domain.
2. **F2 + F3 + F4** — islands, archive, the new `Proposer` protocol +
   `campaign_runner.py` fan-out (genuinely new — `loop/runtime.py` has no
   parallel-agent plumbing to reuse, see F3), LLM breeding. Prove the
   engine on a *toy* proxy with a known optimum before wiring a real
   domain. **Skip or descope this step entirely if F0's Stage 2 already
   settled it** — see step 0.
3. **F5 `dyadic_lyapunov` + `compile_to_claim`** — the POC adapter; the first
   end-to-end campaign that promotes a Lean claim the gate confirms.
4. **F6** — RED-first promotion enforcement + `drill --fansearch` proxy
   audit. **fansearch is not done until a candidate that only fools the proxy
   is demonstrably caught at `baseline`** (author that regression fixture and
   prove it RED).
5. **F7 + F8** — receipts/stats yield-tracking; controller-driven dry-halt.
6. **Second adapter `counterexample`** — proves F5's domain-agnosticism and
   ships the over-claim-auditor capability.
7. **Ablation switch** (§6) into `eval-full.md`'s matrix — the finish line:
   measure whether fansearch-discovered, gate-confirmed claims are *real*
   yield over the authoring baseline, under identical gate discipline.
8. **(§9, deferred) Beyond incremental** — grammar meta-search and
   hub-node targeting. **Explicitly last, not parallelizable with 0–7:**
   both levers trade away the cheap-proxy property that makes F0–F8
   tractable at all, and pointing an unproven mechanism at your
   highest-leverage targets first risks burning them on a mechanism that
   doesn't yet work. Only start §9 once 0–7 have produced at least one
   real, gate-confirmed discovery.

## 8 · What this is, and is not

fansearch is a **discovery** layer that makes recurve author its own claims
when the frontier outruns the backlog — FunSearch's evolve-and-score with a
kernel-checked arbiter bolted where FunSearch has only its evaluator. Its
honest expected yield mirrors FunSearch's: *incremental, verified*
constructions — sharper constants, new monotone functionals for restricted
regimes, machine-caught over-claims — each one a genuine, kernel-confirmed
ledger entry, and none of them a substitute for the human deciding *what is
worth searching for*. The gate remains the arbiter; the frontier remains the
map; fansearch is just the first tool that walks the map on its own.

## 9 · Beyond incremental (deferred until F0–F8 are proven)

§8's "incremental" ceiling is a property of two choices F0–F8 deliberately
makes, not a limit of the mechanism itself: a fixed, human-specified
`building_blocks` grammar (F5), and a target domain (`dyadic_lyapunov`)
chosen *because* it's easy to build a trustworthy cheap proxy for. Both
levers below trade away exactly that cheapness — which is precisely why
they come **last**, after 0–7 have already produced at least one real,
gate-confirmed discovery, never before. Escalating to a harder
proxy-design problem before the basic proxy-guides/gate-decides mechanism
has been shown to work once is backwards.

- **Lever A — meta-search over the grammar, not just within it.**
  `building_blocks` is fixed per domain adapter; the engine only ever
  finds better points inside a space a human already bounded — the exact
  reason FunSearch-style search reliably finds incremental wins (a few %
  on a known bound) and never a qualitatively new construction. A
  step-function version needs a SECOND, higher-level proposer: when an
  island's dry-generations halt (F8) fires, that means the *current
  grammar* is saturated, not that the campaign is done — ask whether the
  grammar itself should be extended (new coupling terms, non-polynomial
  forms, memory-dependent terms), not just re-searched. This needs its
  own proxy, and a harder one: "is this candidate *primitive* worth adding
  to the grammar" is a different question than "is this candidate
  *functional* worth promoting" (F1), and a bad answer here wastes a far
  more expensive resource — redesigning the search space itself — than a
  bad score on one candidate does.

- **Lever B — target high-leverage hub nodes, not isolated leaves.** A
  discovery on an isolated frontier node (one shell-model functional)
  doesn't propagate anywhere. A discovery on a node many *other* claims or
  proofs depend on propagates through all of them at once. A live,
  concrete example, not a hypothetical: `Gronwall.lean`'s own TODO lists
  three blocked generalizations (the inhomogeneous term via variation of
  constants, the weaker liminf slope hypothesis, the norm-valued version)
  that other, currently-stuck proofs elsewhere likely want. `recurve
  frontier`'s ranking already has the information needed to prefer nodes
  like this (how many other claims reference an uncovered id) — campaign
  target selection just isn't using it that way yet. This particular
  change is cheap (which *frontier* ids a campaign points at, not a
  change to the search engine) — it still comes last, because pointing an
  unproven mechanism at the highest-leverage targets first risks burning
  the best opportunities on a mechanism that doesn't yet work.
