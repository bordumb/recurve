# Overflow notes — expansion ideas from the SOTA research

Companion to `recurve-framework.md`. The paper positions recurve against the
adversarially-verified 2025–2026 record; these notes convert that record into a
concrete R&D backlog — things to *build*, in rough priority order. Each item
names its evidence. (arXiv IDs cited here are the same primary sources as in
`references.bib`.)

---

## 1. Probe-hardening engine (highest leverage, directly research-backed)

**What.** A first-class `recurve` mode that treats every probe the way the RLVR
literature now treats reward verifiers: an artifact to be *fuzzed and measured*
before it is trusted.

- **Probe fuzzing.** Generate adversarial states/completions against each probe;
  report a measured **false-positive rate** (probe said GREEN on a wrong state)
  per probe, per suite. Evidence: differential fuzzing found FPRs of 0.56–0.87
  on plausible buggy verifiers, 0.000 on strict references (arXiv:2606.01066).
- **Hardening ablations as gate telemetry.** Track FPR across fix rounds
  (0.833 → 0.233 → 0.000 in the source work) and surface the curve in
  `recurve matrix` — "verifier reliability as a measurable, auditable systems
  property."
- **Isomorphic trap generation.** For claims whose propositions admit
  semantics-preserving transformations, auto-generate an isomorphic variant of
  the state whose verdict must not change; a probe that flips on surface form is
  caught. Evidence: IPT (arXiv:2604.15149), MIT-licensed reference code exists.
- **Differential probes.** Where a stricter reference check exists (a reference
  implementation, a kernel, a slow-but-sound oracle), run both and treat
  disagreement as BROKEN-with-alarm — the differential-testing trick from
  2606.01066 §6, generalized.

**recurve fit.** All of this folds into the adversary's turn under the existing
capture rule: fuzz/perturbation campaigns whose surviving counterexamples become
traps automatically. `recurve drill` is the natural CLI home.

## 2. Trajectory export for training data — with contamination gating

**What.** A `recurve export --trajectories` that emits the run-log as an
RL-ready dataset: (state = ledger+context, action = attempt/decompose/park/revert,
reward = gate verdict), with per-node provenance.

- **The quantified hazard to design against:** ≥1% reward-hacking trajectories
  in SFT data suffices to internalize hacking that resurfaces under RL
  (arXiv:2603.07084). Export must therefore be *gated*: only trajectories whose
  rewards came from trap-validated (and, per item 1, fuzz-measured) probes; refuse
  export for suites whose traps have ever silently stopped failing.
- **Receipts as dataset provenance.** Each exported trajectory carries its
  receipt chain, so a training pipeline can verify — offline — which gate, which
  probe version, and which trap evidence produced every reward. Nobody else's
  agent-trajectory data has signed, re-checkable reward provenance.
- **Branching instrumentation.** Record the counterfactual tree, not one
  traversal: N attempts per claim, alternative decompositions, judge-rejected
  branches. Without this the dataset is a single greedy path (paper §6.1's
  single-path bias).

## 3. The stopping controller as a research vehicle

**What.** The field's named open problem is *detecting judge over-optimization
without ground truth* (arXiv:2502.10325: an ensemble detector was tried and
failed; only mitigations are more rollouts + KL-conservative updates). recurve's
controller occupies exactly this slot with a different answer: the reward is
executable and falsification-tested, so "is the judge being gamed?" reduces to
"are the traps still RED and is measured FPR stable?" — a *measurable* proxy.
Build and publish: controller decision traces (`sense` vectors + decisions) as a
dataset; a study of trap-drift/FPR-drift as an early-warning signal for gaming.
This is a paper-shaped contribution on its own.

## 4. Learned prioritization, kept off the referee surface

**What.** PRMs are genuinely good at *ranking* (survey arXiv:2510.08049) and
genuinely unsafe as *judges* (82%→70% while reward rose, 2502.10325;
DeepSeek-R1's retreat, 2501.12948). recurve can use the good half safely: a
learned value model advising `recurve next` — which RED claim is most closeable,
which decomposition looks most promising — while verdicts remain exclusively
probe-decided. Advisory-only by construction: the write boundary already makes
this separation enforceable, and the run-log (item 2) is exactly the training
data for it. This would make the loop cheaper without touching its trust story.

## 5. Adversary economics and diversity

**What.** The separation invariant says spend adversary turns only on
irreducible judgment; nothing yet says *how many* or *how diverse*.

- Budgeted adversary scheduling: per-wave adversary quotas tied to churn (new
  claims, changed probes), not calendar.
- Diversity requirements: different model, different prompt family, output-only
  context — measured decorrelation between adversary and actor failure modes
  (the §2.9 requirement, made quantitative).
- Capture-rule metrics: objections raised vs. traps successfully deposited —
  an adversary whose objections rarely convert to discriminating traps is
  nitpicking; one whose traps often catch later regressions is under-used.

## 6. A hands-on audit of industry harnesses (the unconfirmed cell)

**What.** The research produced *no verifiable claims either way* about whether
Inspect (UK AISI), OpenAI Evals, METR task standards, or Anthropic's eval
frameworks implement falsification-tested checks or actor/referee separation.
That's an absence of evidence, not evidence of absence — and it's cheap to
resolve: read the four codebases directly and publish a feature-by-feature
comparison against the five mechanisms in paper §5.5. Either outcome is
valuable: confirmed absence sharpens the positioning; discovered presence names
a collaborator/adopter.

## 7. Verifier-gaming benchmark built from recurve traps

**What.** The field builds testbeds to *measure* harness manipulation
(Countdown-Code 2603.07084; SpecBench 2605.21384; BenchJack 2605.12673). recurve
sits on a growing corpus of real traps — known-bad states with verified RED
verdicts across real projects. Package them as a public benchmark: "can your
agent/verifier distinguish these known-bads from the adjacent correct states?"
This flips the trap library from an internal discipline into a community
artifact, and it is the natural place to demonstrate item 1's FPR telemetry.

## 8. Evidentiary-hygiene tooling for the gate's own statistics

**What.** The RLVR measurement critique (2509.21882; COLM 2025 "Sober Look")
found headline gains dissolving under budget-matched evaluation and
contamination probes. recurve's `stats`/`report` should be constitutionally
immune: report close-rates with attempt budgets attached; flag claims whose
probes were authored after seeing the implementation (contamination analog);
never aggregate across suites with different trap discipline. Cheap to build,
and it makes the run reports citable in the way the field's own numbers
currently are not.

## 9. Deferred paper content (kept out for scope, still worth writing)

- **Worked multi-cycle example** — a full appendix walking one claim through
  decompose → park → adversary trap → close, with real ledger diffs.
- **Formal-gates related work** — the Lean/AlphaProof lineage yielded no
  *verified* claims in the research pass (area f); a dedicated pass with
  primary-source reading would fill §5's acknowledged gap.
- **Threat model appendix** — precise statement of what the write boundary does
  and does not defend against (sandbox escape, collusion between actor and
  adversary instances, supply-chain edits to the probe engine), with the
  honest boundary: tamper-*evident* beyond it, not tamper-*proof*.
- **Controller formalization** — the stopping controller's decision function as
  a small verified artifact of its own (it is deterministic; it could itself be
  claim-gated).
