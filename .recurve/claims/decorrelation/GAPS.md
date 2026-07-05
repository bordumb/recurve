# decorrelation — what backed a GREEN, probed

> `docs/plans/oracle-strength-and-decorrelation.md` R1 + R3: recurve's own
> ledger currently cannot distinguish a GREEN that a same-model self-authored
> probe approved from a GREEN that survived an independent check. This suite
> covers the two requirements buildable with mechanisms that already exist
> (`drill --diff`, `drill --fuzz`, `oracle_waiver`, trap presence) — no new
> port/protocol. R2's cross-model adversary, R4's reversal log, and R5's
> governor build on `docs/plans/ablation-infra.md`'s ports/adapters and live
> in the `ablation` suite; the O6-incident regression fixtures (R2 claim-level,
> R5 run-level) close this suite once `ablation` exists to run them against.

## Conventions

`missing-surface` claims about `recurvelib.analysis.oracle_tier`, `reads:
none` — each probe imports the real engine, constructs synthetic `Gap`s and
evidence, and checks the derivation/rendering against a named oracle. A trap
loads a `broken_*.py` alternate of the one function under test from its
fixture directory, the same pattern `stopping`/`plumbing`/`self_recursion`
already use.

## DC-1 — oracle tier: recorded, derived, rendered, honest about what backs it

Every claim's GREEN carries a recorded **oracle tier** — `self_probe <
trap_hardened < fuzz_measured < adversary_reviewed < adversary_cross_model <
differential_checked_llm < differential_checked_mechanical < kernel_verified`
— derived automatically from which passes actually ran against it, never
hand-set. `recurvelib.analysis.oracle_tier.derive_tier` computes it from the
gap's static shape (trap presence, `reference` field) plus a **tier-evidence
log** (`.recurve/state/tier_evidence/<suite>.jsonl`, distinct from the ledger
and from the run-record dataset `drill` deliberately never pollutes) that
records whether `drill --diff`/`--fuzz` actually ran against this gap, and
what a differential reference actually *is* (mechanical ground truth vs.
LLM-authored) — checked structurally (an allowlist glob plus a deny-pattern
scan for agent/LLM invocation in the reference's own source), never merely
declared. `recurve ledger` and `recurve show` render the tier.

Negative space: a `reference:` field present with no `diff` evidence
recorded must not render a `differential_checked_*` tier (the field's mere
existence is not evidence). A reference that is itself LLM-authored must not
render `differential_checked_mechanical`, even if a config author mislabels
it. A `gaps.yaml` entry carrying an explicit `tier:` key must fail to parse —
tier is never a ledger field, only ever a derived one. An existing ledger
entry with a trap and no other evidence renders `trap_hardened` (today's
actual meaning) with no migration required.

## DC-2 — surface the weak-oracle question during authoring, not after

A claim that closes on `self_probe` or `trap_hardened` alone — no
`reference`, no adversary evidence, no `oracle_waiver` — surfaces an
advisory note in `recurve ledger`, visible, never blocking GREEN.
`recurvelib.analysis.oracle_tier.needs_oracle_advisory` derives this the same
way `derive_tier` does, from the same evidence log, so the two can never
disagree about what evidence exists.

Negative space: a `reference:` field added after the fact purely to suppress
the advisory, with `drill --diff` never actually run against it, must still
show the advisory — the anti-gaming trap is the same one DC-1 exercises,
applied to the advisory instead of the tier.

## DC-3 — the O6-incident regression fixture, at claim level (R2's acceptance criterion)

Replays the real incident recorded in `eval/runs/o6/results.jsonl`
(`claude-sonnet-5-A3-...`: `declared_done=true`, `gate_outcome="declared"`,
`terminal_state.stop_reason="gate_green"`, but `oracle_verdict="fail"`) using
the REAL `cross_model` adversary adapter (`ablation` suite AB-6) and the
REAL, untouched `capture()` rule — not stubs. A toy claim shares the actual
incident's bug class (BigCodeBench/13's FTP task: "return every file
ATTEMPTED, even failed ones" — the wrong solution silently drops failed
attempts, and its same-model self-authored probe only exercises the happy
path, so the two agree). The claim closes GREEN on the self-authored probe
alone; the `cross_model` adversary — a genuinely different reviewer identity
— disagrees, and its proposed counterexample passes `capture()`'s
discrimination test (RED on the wrong solution, GREEN on a correct one),
proving the mechanism would have caught what actually happened.

Negative space: a reviewer sharing the actor's own served identity (a
same-model pass masquerading as `cross_model`) must be refused by the
identity check, not mistaken for a real cross-model pass.
