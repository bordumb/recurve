# Plan: from *sound* to *complete* — synthesis, the coverage gate, and intent fidelity

> Status: design / proposed phase. Extends the core model in `docs/plan.md` (claims, probes, the monotone
> gate, traps, the promotion ceremony). Greenfield: the coverage subsystem here is specified clean-room
> against recurve's own primitives — it is **not** a port of any external tool.

---

## 0. The gap this closes

recurve today is **sound but not complete.** It guarantees that the *claimed* parts of a change are right
(a probe is GREEN, its trap is RED, the gate never un-proves a closed claim). It says **nothing about the
unclaimed parts.** Everything outside the contract is invisible to the gate.

Three failure modes fall directly out of that one gap, and they are the reasons recurve is currently only
usable for narrow, pre-specified, binary work:

1. **Authoring is the overhead.** A user must hand-write every claim *and* its probe. You can state
   "make `X` produce `ABC`," but not "figure out the right way to do `X`." The hard cognitive work —
   decomposing a goal into checkable promises — stays entirely with the human. The tool relocates effort
   rather than removing it.
2. **Silent holes.** Because only claimed surface is gated, a change can be fully GREEN while large parts of
   the work are unbuilt or wrong. A light user, writing few claims, gets a confidently-green result riddled
   with gaps — and never sees them.
3. **The wrong thing, gated green.** Claims are a *lossy proxy* for intent. An agent can satisfy the letter
   of a contract and miss its point.

And the sharpest version of the problem: **the gate is an incentive.** An agent optimizes toward what is
measured. So the contract doesn't merely *fail to cover* the vague parts — it actively pulls the agent
*away* from them (Goodhart). Soundness, left alone, manufactures confident incompleteness.

**This plan adds a completeness layer on top of soundness — without weakening soundness — and makes the
residual gap *visible and shrinking*, never pretends it is zero.** The product promise shifts from the
over-broad "make truth executable" to the precise and honest:

> recurve turns a vague goal into a reviewed contract, **guarantees the contract**, and **tells you exactly
> what the contract does not cover** — and shrinks that uncovered set every cycle.

That final clause is the whole fix.

---

## 1. Principles (continuous with recurve's existing discipline)

The completeness layer reuses recurve's epistemics rather than inventing parallel ones:

- **Totality.** Just as a probe's outcome is total (`GREEN / RED / BROKEN`, any other exit coerced to
  `BROKEN`), every point of the target's surface has a total coverage verdict:
  `COVERED / UNCOVERED / DEFERRED / UNMEASURABLE`. "I could not determine coverage" (`UNMEASURABLE`) is the
  coverage analogue of `BROKEN` — it blocks the gate; it never silently reads as covered.
- **Measurements, not intentions.** Coverage is *observed* — derived from instrumented probe runs, recording
  which surface a probe actually exercised — never declared. A claim that *says* it covers `f` but whose
  probe never touches `f` does not cover `f`.
- **Monotone.** Coverage ratchets one way. A surface point that was `COVERED` and becomes `UNCOVERED` is a
  regression and fails the gate, exactly as a closed claim regressing does. The **deferred set is explicit
  and may only shrink** — a deferral must be re-justified to persist.
- **Greenness = soundness ∧ completeness ∧ fidelity** (see §5). A release is green only when the claimed
  parts pass, the unclaimed parts are accounted for, and the goal-level counterexamples are still rejected.
- **Honest lane.** Verification earns its keep where being wrong is expensive (correctness, security,
  regression-prone invariants). For open-ended *design* exploration the gate is friction, and recurve should
  say so and stand down (§7).
- **Separation of refereeing** (binding invariant — `separation-of-refereeing.md`). No actor judges its own
  work. Correctness is refereed by probes; the proposer/critic of §2 and §4 is the *adversary* of that
  invariant — opposing-incentive, no shared context with whatever closes the claims — and its objections
  count only once **captured as traps**. A judgment that cannot become a discriminating counterexample is
  discarded.

---

## 2. Subsystem A — Synthesis: turn a goal into a *reviewed* contract

*Fixes failure mode 1 (authoring overhead / spoon-feeding).*

Today the human authors claims. Flip it: **the human states a goal in prose and curates a proposed
contract.** Review is far cheaper than authoring, and curation is judgment the human is good at.

- **The proposer is a role, not the builder.** A dedicated *adversarial proposer* drafts the contract from
  the goal: the claims, their traps, the surface it expects to cover, and the goal-level counterexamples
  (§4). It is deliberately **separate from whatever closes the claims** — if the same actor proposes and
  satisfies, it converges on easy claims. The proposer's incentive is to surface the invariants a builder
  would rather not have to meet. (This is the `trap` instinct — "a probe never seen to fail is not evidence"
  — lifted to the contract level: a *contract* the builder can't fail is not a spec.) This proposer **is** the
  adversary of `separation-of-refereeing.md`: it shares no context with the builder, and any objection it
  raises counts only once it is deposited as a goal-level trap (§4) — prose it cannot turn into a
  discriminating counterexample does not count.
- **Properties over examples.** A proposed claim should prefer an *invariant over a class of inputs*
  ("for all inputs in class `C`, the output satisfies `I`") to a single example ("`f(2) == 4`"). Invariants
  are harder to game and, backed by property/fuzz probes, **explore the input space the human didn't
  enumerate** — which is precisely where the holes live. One property-probe subsumes dozens of example
  probes.
- **Curation is the cheap checkpoint.** The human edits the proposed contract and answers one question:
  *"if every one of these is green, did I get what I asked for?"* (the fidelity gate, §4). Minutes, not
  hours, and it happens *before* any building.
- **Promotion is unchanged.** A proposed claim enters the ledger only after a real probe run with quoted,
  dated output. Synthesis lowers the *cost* of producing claims; it does not lower the *bar* for a claim to
  count. Measurements, not intentions, still rules.

Mechanically this extends the existing `claimify` path into a pipeline:
`goal (prose) → proposer drafts contract → human curates → promotion ceremony → baseline`.

---

## 3. Subsystem B — The coverage gate: map the surface, surface the *uncovered*

*Fixes failure mode 2 (silent holes / unsafe light usage). This is the highest-value change because the
holes are silent — and silence is the dangerous failure for a trust tool.*

The idea: measure **what the change actually is** (its surface) against **what the contract claims**, and
make the delta a first-class, gated, fed-back artifact.

### 3.1 The surface map (greenfield, adapter-based, deterministic)

- A **surface point** is the unit of "something that could be claimed": an abstract record
  `{ id, kind, location, weight }` where `kind` ∈ {behavior, entry point, branch, effect, …} and `weight`
  is an optional risk/sensitivity score so the frontier can be ranked, not just listed.
- The surface is produced by **language/runtime adapters behind a generic core** — `core` knows only the
  abstract `surface point`; an `adapter` knows how to extract them from a given stack. Adapters are
  pluggable; the core never assumes a language.
- Extraction is **deterministic and LLM-free**, like a probe: same input → same surface map, diffable and
  versionable. The map is a ledger artifact so coverage *regressions* are detectable across cycles.

> Greenfield note: design the surface model from recurve's verdict totality and "measurements not
> intentions" on day one. Do **not** retrofit an external capability/coverage mapper — its abstractions
> (and its couplings) will fight the claim/probe/gate model. Start from the `surface point` type and the
> coverage verdict, and build outward.

### 3.2 Coverage as a *measurement*

A claim **covers** a surface point iff its probe *demonstrably exercises* that point during a real run
(instrumentation records the touch). Two grades, kept distinct so weak never masquerades as strong:

- **Strongly covered** — a claim whose probe exercises the point **and** whose trap demonstrates that point
  *matters* (the counterexample at that point is rejected). This is real evidence the behavior is pinned.
- **Weakly covered** — a probe merely *touches* the point (it ran through it) without a trap proving the
  behavior there. Touching a line is not verifying it; report weak coverage as a distinct, lesser state.

Per surface point, the total verdict:

| verdict | meaning | gate effect |
|---|---|---|
| `COVERED` (strong/weak) | a passing claim exercises it | passes |
| `DEFERRED` | explicitly marked out of scope — a *recorded decision* with a reason | passes, but counted and re-justified each cycle |
| `UNCOVERED` | no claim reaches it | **blocks** the gate |
| `UNMEASURABLE` | instrumentation cannot determine coverage | **blocks** the gate (the `BROKEN` analogue) |

### 3.3 The frontier, and closing the incentive loop

- **The frontier** = the set of `UNCOVERED` points, ranked by `weight`. This is the visible gap that today
  is invisible. Even before any gating, *surfacing the frontier alone* makes light usage **safe**: a user
  who writes three claims now sees "and here are the 40 surface points nothing covers," instead of a false
  green.
- **Claim-or-defer, never ignore.** To go green, every `UNCOVERED` point must become either `COVERED`
  (author the claim) or `DEFERRED` (explicitly, with a reason). There is no third, silent option.
- **The frontier *is* the next cycle's work.** Because the gate is an incentive, the uncovered list must
  feed back into burndown as candidate RED claims-to-author (or defer decisions). The agent is rewarded for
  *shrinking the frontier*, not only for passing the claims it was handed — which is exactly the pull that
  counteracts Goodhart.

---

## 4. Subsystem C — Intent fidelity: claims near intent, catch the *wrong thing*

*Fixes failure mode 3 (gamed/letter-not-spirit contracts).* Full coverage still permits satisfying the
letter and missing the point. This is the alignment problem in miniature — not fully solvable, but
mitigable, and recurve already owns the right primitive.

- **Reuse traps at the *goal* level (no new primitive).** A trap is a known-bad the probe must reject; recurve
  already treats a trap going GREEN as "a gate failure of the highest order." Lift this to the goal: a
  **counterexample contract** — a small set of scenarios that, if they pass, mean *we built the wrong
  thing*. (Goal "rate limiter" → counterexample "one tenant can drain the whole pool.") If every positive
  claim is GREEN **and** any goal-counterexample also passes → `DIVERGENT`: the contract missed its point.
- **Weight the contract toward acceptance.** Prefer end-to-end / behavioral claims (intent-near, hard to
  game) over unit claims (easy to game). The proposer should be required to produce a minimum quota of
  acceptance-level claims; a contract that is all unit claims is a smell.
- **Gate the human on the *contract*, before burndown.** The cheapest place to catch the wrong thing is a
  short human review of the *spec* — "is this contract a faithful proxy for my intent?" — *before* the agent
  builds hours of the wrong code. Reviewing the contract, not the output, is the leverage point.

---

## 5. Greenness, redefined

A cycle (and a release) is **GREEN** iff all three hold, each reported with a precise, differentiated reason
on failure:

1. **Soundness** — every claim's probe is `GREEN` and every claim's trap is `RED` (still rejecting its
   counterexample). *(unchanged from today.)*
2. **Completeness** — every surface point is `COVERED` or `DEFERRED`; none `UNCOVERED`, none `UNMEASURABLE`.
3. **Fidelity** — every goal-counterexample is `RED` (the wrong-thing scenarios are rejected), and the
   human contract-review gate is satisfied.

Any failure yields a named cause: *which claim, which surface point, which counterexample.* And the green
release **ships with its coverage map + deferral list + counterexample results** in the receipt — the honest
"here is what I guarantee, here is what I don't."

---

## 6. The cycle, end to end

```
1. Goal              — the user states intent in prose.
2. Synthesis         — the adversarial proposer drafts the contract:
                       claims + traps + expected surface + goal-counterexamples.
3. Curate + Fidelity — the human edits the contract and signs the "faithful to intent" gate. (cheap, pre-build)
4. Surface           — the deterministic map is computed; the frontier (uncovered, ranked) is shown.
5. Burndown          — the agent closes RED claims AND shrinks the frontier (claim-or-defer each point).
6. Gate              — GREEN iff soundness ∧ completeness ∧ fidelity (§5); the residual is explicit.
7. Receipt           — the release carries its coverage map, deferral list, and counterexample results.
```

---

## 7. Honest limits (state these in the product, don't paper over them)

- **Completeness is asymptotic.** The deferred/uncovered set is never *guaranteed* zero. The promise is
  "visible and shrinking," not "total." A receipt that claims total coverage is itself a smell.
- **Coverage is a proxy.** Touching a surface point is not verifying its behavior — hence the strong/weak
  distinction (§3.2). Do not let weak coverage be sold as strong.
- **Synthesis can propose bad claims.** The adversarial proposer reduces this, but human curation (§2) is
  the backstop, not an optional step. A contract no human reviewed is a draft.
- **Not for open-ended design.** recurve is for invariant-rich, high-stakes work. For genuine exploration
  ("find the best architecture") the gate should stand down — and recurve should *detect and say* when a
  goal has too few stable invariants to gate, rather than forcing a brittle contract onto creative work.
  Refusing to gate is sometimes the honest verdict.

---

## 8. Suggested build order

Sequenced so the **biggest safety win lands first**, automation second:

- **P1 — Surface + frontier (read-only).** One adapter; compute the surface map; show the ranked frontier.
  No gating yet. *This alone* converts silent holes into a visible list and makes light usage safe.
- **P2 — Coverage measurement.** Instrument probe runs; derive `COVERED` (strong/weak) / `UNCOVERED` /
  `UNMEASURABLE` per point.
- **P3 — The completeness gate.** Greenness = soundness ∧ completeness; claim-or-defer; monotone coverage
  with regression detection; frontier feeds burndown.
- **P4 — Synthesis.** The adversarial proposer + property/fuzz probe templates; curate-don't-author.
- **P5 — Intent fidelity.** Acceptance-claim quota + goal-counterexamples (trap-reuse) + the pre-build
  contract gate.

P1 is shippable on its own and addresses the most dangerous complaint (silent holes) before any of the
harder machinery exists.

---

## 9. Why this is the right shape for recurve specifically

The completeness layer is not a feature bolt-on; it is the **dual** of recurve's existing half. Soundness
asks "are the claimed things right?" Completeness asks "are the right things claimed?" Together they make the
gate report not just *"this is correct"* but *"this is correct, and here is the precisely-bounded set it
says nothing about"* — which is the only honest thing a verification tool can promise, and the exact thing a
user needs to trust an agent with vague work instead of only binary work.
