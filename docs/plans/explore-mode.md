# Explore mode: invert the trap — a second gradient beside GREEN

## 0. What this is, and what it is not

recurve today has exactly one currency: **GREEN**. A claim closes when its probe passes and its trap has been
seen RED. That single gradient is what makes closure *trustworthy* — and it is also why an agent driving
recurve **cannot explore the unknown**. Facing a genuinely-open problem, it decomposes down to the
already-provable, closes those, correctly labels the hard remainder "not known," and **parks**. That is not
timidity; GREEN is the only thing it is rewarded for, and the unknown space contains none of it.

This layer adds the **second gradient** — one that rewards walking *into* the unknown — **without** letting
back in the fabrication the gate exists to prevent. It is **not** a new oracle and **not** a way to certify
unproven results. A conjecture that survives here is a **lead**, never a truth; only the kernel/probe still
mints GREEN. What changes is that the *search frontier* becomes as legible and un-gameable as the finished
claim already is — because it is scored by the **same falsification discipline**, pointed the other way.

Origin: bordumb/recurve#27 ("how do we get an agent to explore the unknown rather than give up?").

## 1. The inversion

A **trap** is a known-bad that a probe **must reject**. Seeing it go RED proves the probe can tell true from
false — it *can* fail — and that is what licenses trusting its GREEN. A trap is a bullet the probe must dodge;
it **guards a claim we believe true.**

The exploration currency is the mirror image:

> A **conjecture** earns standing not by being proven, but by **surviving a battery of genuine attempts to
> falsify it.**

A **falsifier** is a bullet fired at a conjecture we do *not* yet know:

- If it **lands** — produces a counterexample — the conjecture is **FALSIFIED**: pruned, and recorded (a dead
  lead still maps the space and prunes the tree).
- If a battery of *potent* falsifiers all **miss**, the conjecture **SURVIVES** — and a surviving conjecture
  is a **trustworthy lead**, because it withstood real attempts to destroy it, not a model's optimism.

Traps make **closure** legible; falsifiers make **exploration** legible. Same primitive
(falsification-before-trust), both halves of research: *is this finished thing true?* and *is this unfinished
direction still alive?*

## 2. The soundness invariant: no survival without a demonstrated kill

A conjecture that "survives" only because nobody tried hard is worthless — the precise failure mode recurve
exists to kill. So the falsifier battery is held to the **exact trap discipline, mirrored**:

- A probe is admissible only once its trap has been **seen RED** (it demonstrably *can* fail).
- **A survival is admissible only once its falsifier battery has been seen to KILL** — it must first destroy
  seeded **calibration decoys** (known-false conjectures planted to prove the battery has teeth).

So "survived N falsifiers" is shorthand for "survived N falsifiers *that provably kill things*." A battery
that cannot kill its decoy makes the conjecture **BROKEN** (unmeasurable), never SURVIVING — identical to the
verdict on an un-trapped probe. **This invariant is load-bearing; without it, explore mode is a
guess-amplifier and must not ship.**

## 3. Graded survival

Survival is **evidence, never proof**, and its strength is graded exactly like the framework paper's oracle
spectrum (strongest where it bottoms out in a sound oracle, weakest where it is an authored artifact):

| Falsifier kind | Strength of a survival against it |
|---|---|
| Numerical counterexample search (simulate; measure the candidate quantity) | **weak** — unsound proxy, a hint |
| Symbolic sign/monotonicity check; random-instance fuzz | **medium** |
| Adversarial agent constructing a counterexample or reducing to a known-false | **medium–strong** |
| Partial proof / restricted-case proof in the kernel | **strong** — bottoms out in the oracle |

A conjecture publishes a **survival profile** — how many of each kind, at what strength, over how many
independent seeds — **never a single "safe" bit**. Numeric survivals are surfaced marked *unsound proxy*. Only
a full kernel-clean proof **promotes** a conjecture to GREEN; a surviving conjecture stays RED and is labeled
a lead.

## 4. Data model

A new claim `class: conjecture`, in the same ledger as provable claims.

- **`gaps.yaml`**: `class: conjecture`, a precise `statement` (a Prop / estimate / inequality), `status`
  (§6), a `survival_profile`, and `covers`/`unlocks` edges like any claim (a lead must lead *somewhere* — §8).
- **`falsifiers/`** — the structural inverse of `traps/`. Each subdirectory is one kill-attempt:
  - a **kind** (numeric | symbolic | fuzz | adversary | partial-proof),
  - an **executable** returning `KILLED` (counterexample, with the witness recorded) or `SURVIVED`,
  - the **calibration decoys** it must KILL to be admissible (§2),
  - a **seed/angle** descriptor, so independence can be enforced (§8).
- **The matrix / gate** grows conjecture rows:
  `SURVIVING(profile) · calibrated · N falsifiers · 0 kills` | `FALSIFIED(witness: …)` |
  `PROMOTED(kernel-clean → GREEN)` | `BROKEN(battery failed calibration)`.

## 5. The explore loop and the reward rule

`recurve explore` is a loop mode **beside** the closure loop (`matrix --gate`), sharing the ledger. An agent
proposes conjectures, then spends its effort trying to kill its own and others'. It is scored on
**surviving-falsification**, not on GREEN:

1. **Propose** a novel conjecture whose battery passes calibration — small credit.
2. **Survive** each additional *independent, potent* falsifier — the main gradient (more/stronger survived =
   stronger lead).
3. **Falsify** any conjecture (its own or another's) — also credited; a dead lead is real information.
4. **Promote** a surviving conjecture to a kernel-clean proof — the jackpot; hands it back to the closure loop
   as GREEN.

This gives an agent a reason to generate and stress-test candidate mechanisms, auxiliary quantities,
reformulations, and model-problem reductions — while the §2 calibration guarantees that a "promising lead"
coming out of recurve is one that genuinely resisted destruction.

## 6. Lifecycle

```
proposed ──calibration passes──▶ surviving ──kernel-clean proof──▶ PROMOTED (GREEN, handed to closure loop)
   │                                │
   │ battery fails calibration      │ any falsifier KILLS
   ▼                                ▼
 BROKEN                          FALSIFIED (witness recorded, pruned, tree updated)
```

`surviving` is not terminal: strength **decays** with time and with changes to its dependencies (§8), so a
lead left un-retested drifts back toward `proposed` and must earn its profile again.

## 7. How it composes with the closure loop

- **One ledger, two gradients.** Closure scores GREEN; explore scores survival. The stopping controller reads
  both — "no open provable work *and* no surviving lead worth promoting" is a stronger halt than either alone.
- **Promotion is the bridge.** A conjecture with a strong-enough survival profile (threshold TBD, §8) is
  emitted as a *prioritized proof target* for the closure loop — exploration feeds verification.
- **A sound home for `fansearch`.** Today's numeric proxy campaigns are throwaway and unsound; here a numeric
  survival is a first-class, weak, honestly-graded falsifier result in the ledger, with provenance
  (cf. `fansearch-proxy-provenance.md`).
- **Adversary reuse.** The existing review/adversary path (`REVIEW.md`) is a strong falsifier *kind*; its
  objection is captured as a re-runnable kill-attempt — the capture rule, applied to conjectures.

## 8. Open design questions

- **Falsifier independence.** Prevent N near-identical numeric runs from inflating a profile — require
  *diversity* of kind/seed/angle, and measure it the way the paper measures fuzz false-positive rates.
- **Decay function.** How fast does survival strength decay in time / on dependency change? What reverts a
  lead to `proposed`?
- **Promotion threshold.** Which survival profile makes a conjecture a prioritized proof target?
- **Anti-gaming.** Block trivially-unfalsifiable-but-useless conjectures: require a real `covers`/`unlocks`
  edge to an open claim, and penalize conjectures whose only falsifiers are the weakest kind.
- **Cross-agent trust.** A conjecture proposed by one agent and falsified by another is the ideal loop; how is
  credit split, and how are collusion / degenerate equilibria avoided?

## 9. Milestones

1. **Spec + schema** — this doc lands; `conjecture` class and `falsifiers/` layout specified in the developer
   guide.
2. **Calibration gate** — a falsifier battery is admissible only after KILLing its seeded decoys; else
   `BROKEN`. (The load-bearing invariant, §2 — build this first, prove it can't be bypassed.)
3. **Graded profile in the matrix** — `survival_profile` surfaced; numerics marked unsound-proxy.
4. **`recurve explore` loop** — the reward rule (§5), promotion path to the closure loop.
5. **Worked example** — the open depletion / coherence-ratio estimate from the `navier_stokes` suite: propose
   a candidate monotone quantity, calibrate + run the battery, land a graded survival profile — RED, surviving,
   honestly a lead. This is the acceptance test: exploration made legible on a genuinely-open target.
