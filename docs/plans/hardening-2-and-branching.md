# PRD — waiver-honoring drill, isomorphic & differential hardening, branch capture

> Source: the self-hosted run behind `docs/plans/hardening-and-trajectories.md`
> (its recorded follow-ups), and `docs/papers/recurve-framework.md` §7.1–§7.2.
> Three threads: fix the referee disagreement the last run surfaced (the drill
> fails on a SKIP the gate correctly waives); complete the probe-hardening
> program (the fuzz pass shipped the "reject generated known-bads" half — this
> adds the "hold verdicts on semantics-preserving variants" half plus reference
> oracles); and remove the flywheel's single-path bias by letting cycles record
> the branches they did NOT take. As before: every behavior is a config/CLI
> **parameter**, not a policy — users tune cost and strictness to their budget.

---

## F1 — The drill honors declared oracle waivers

**Purpose.** The gate (`matrix`) treats a probe's SKIP under a **declared**
`oracle_waiver` as visible, non-blocking debt (`is_waived_skip`,
`recurvelib/conformance.py`), and excludes such claims from the trap pass. The
drill does not: the same SKIP fails the whole audit ("a guard would bless its
own defect") on an otherwise clean fleet — reproduced on this repository, where
one claim's external oracle is absent at a standalone checkout. Two referees,
one fact, two verdicts. The drill must mirror the gate's semantics.

**Contract.**

- **F1.1 A waived SKIP is debt, not failure.** In `recurve drill`, a trap run
  whose outcome is SKIP on a claim that **declares** `oracle_waiver` is
  reported as an oracle-waived counterexample and counted beside the existing
  waived-guards figure in the drill summary; it does not fail the drill.
  - *Observable:* on a project whose one closed claim has a trap and a probe
    that exits 3 (oracle absent) with `oracle_waiver` declared, `recurve
    drill` exits 0 and its summary counts 1 oracle-waived counterexample.
  - *Counterexample (wrong):* the same project failing the drill with "a guard
    would bless its own defect", or the waived SKIP silently dropped from the
    summary (invisible debt).
  - *Bounded:* the drill's trap loop; claims with a declared `oracle_waiver`.
- **F1.2 An undeclared SKIP still fails.** A trap run whose outcome is SKIP on
  a claim **without** `oracle_waiver` remains a drill failure — a probe can
  never dodge the audit by reporting its oracle absent unless the claim
  declared that possibility up front.
  - *Observable:* the same project minus the `oracle_waiver` line makes
    `recurve drill` exit 1, naming the SKIPping trap.
  - *Counterexample (wrong):* an undeclared SKIP treated as waived (the dodge
    the gate already forbids, reopened through the drill).
  - *Bounded:* the same trap loop; no other verdict's handling changes.

## F2 — Isomorphic variants and reference oracles

**Purpose.** The fuzz pass measures whether a probe rejects *broken* variants.
Its dual is unmeasured: whether a probe's verdict **holds** on
*semantics-preserving* variants — a probe that flips on a cosmetic rewrite has
latched onto surface form, not meaning. And where a stricter reference oracle
exists, disagreement between it and the probe should be an alarm, not a
coincidence nobody checks. Both are opt-in audits, priced by knobs.

**Contract.**

- **F2.1 Isomorphic generator convention.** A claim may ship an executable
  `probes/<id>.iso.sh`. Called with env `ISO_OUT=<dir>` and `ISO_N=<n>`, it
  writes up to `n` variant fixture directories under `ISO_OUT`, each a
  semantics-preserving restatement of the state the probe checks.
  - *Observable:* running the generator with `ISO_N=3` produces up to 3
    directories under `ISO_OUT`; `recurve drill --iso` consumes them; claims
    without a generator are untouched and report nothing.
  - *Counterexample (wrong):* a drill that runs isomorphic generators when
    `--iso` was not given, or ignores their output when it was.
  - *Bounded:* closed claims that ship a `probes/<id>.iso.sh`.
- **F2.2 Verdict invariance, measured.** `recurve drill --iso` runs each
  iso-capable closed claim's probe once per variant with `ISO_FIXTURE` set to
  that variant. The probe's verdict on a variant must equal its verdict on the
  true state (GREEN, for a closed claim); a differing verdict is a **flip**.
  The drill prints, per probe, `iso flips f/n`, and exits nonzero iff any
  probe's flip rate exceeds the configured threshold.
  - *Observable:* a form-insensitive probe yields `iso flips 0/n` and exit 0;
    a probe that keys on surface form (e.g. matches the exact spelling an
    isomorphic variant rewrites) yields a nonzero flip count and exit 1.
  - *Counterexample (wrong):* a drill reporting 0 flips for a probe that
    turns RED on a semantics-preserving variant, or passing overall despite a
    probe exceeding the threshold.
  - *Bounded:* iso-capable closed claims in the selected suite.
- **F2.3 Isomorphic knobs.** Off by default (`--iso` enables). `[drill] iso_n`
  (default 8) bounds variants per probe; `[drill] iso_flip_max` (default 0.0)
  is the failure threshold.
  - *Observable:* without `--iso` the drill's output and exit code are
    unchanged; with `iso_n = 2` at most 2 variants are consumed per probe
    (the reported denominator is 2); with `iso_flip_max = 1.0` a flipping
    probe is reported but no longer fatal.
  - *Counterexample (wrong):* isomorphic runs without `--iso`; an ignored
    `iso_n`.
  - *Bounded:* the `[drill]` config table and the `drill` subcommand surface.
- **F2.4 Reference oracles (differential probes).** A claim may declare
  `reference: probes/<id>.ref.sh` in its ledger entry — a stricter or slower
  check of the same proposition. `recurve drill --diff` runs, for each closed
  claim declaring one, both the probe and the reference against the true
  state; **disagreement** (one GREEN, the other RED) is reported as an alarm
  naming both verdicts and fails the drill. Claims without a `reference` are
  untouched. The field survives the baseline ceremony (drafts carrying
  `reference` keep it on promotion).
  - *Observable:* a project whose probe says GREEN while its declared
    reference says RED makes `recurve drill --diff` exit 1 with a
    disagreement line naming the claim; agreeing checks pass; without
    `--diff` the drill is unchanged.
  - *Counterexample (wrong):* a disagreement reported as agreement (or
    silently swallowed), or a `reference` declaration dropped by baseline
    promotion.
  - *Bounded:* closed claims declaring `reference`; the drill surface only —
    gate semantics do not change.

## F3 — Branch capture: record the road not taken

**Purpose.** A run-record stores the path taken; the counterfactuals — the
decomposition considered and rejected, the attempt abandoned — are lost. For
the trajectory dataset this is the single-path bias: a corpus of only-winners
teaches selection nothing. F3 makes branch capture a first-class, additive part
of the record.

**Contract.**

- **F3.1 Records may carry branches.** The run-record schema gains an optional
  `branches` field: an array of objects, each with `kind` (one of `attempt`,
  `decomposition`, `approach`), `description` (what the branch was), and
  `rejected_because` (why it was not taken). The field is additive: records
  without it remain valid, and `recurve record append` accepts records with it
  (schema-validated — a branch entry missing `rejected_because` is rejected).
  - *Observable:* `recurve record append` accepts a record carrying two
    well-formed branch entries and stores them verbatim in records.jsonl;
    the same record with a branch entry lacking `rejected_because` is
    rejected with a schema error.
  - *Counterexample (wrong):* branch entries silently stripped on append, or
    a malformed branch entry accepted (the dataset stays clean or it is
    worthless).
  - *Bounded:* the shipped run-record schema and the append path; no existing
    required field changes.
- **F3.2 Trajectories export branches.** `recurve trajectories` includes each
  row's `branches` (an empty array when the record has none), under the same
  provenance and contamination gating as the rest of the row, preserving the
  export's determinism (byte-identical re-runs).
  - *Observable:* on a project whose records include one branch-carrying
    cycle, the exported row for that cycle contains its `branches` verbatim,
    rows without branches carry `"branches": []`, and two consecutive exports
    are byte-identical.
  - *Counterexample (wrong):* branches dropped from export, or export
    determinism broken by the new field.
  - *Bounded:* the trajectories serializer; the contamination gate's
    verified/unverified logic is unchanged.

---

## Non-goals (this PRD)

- No automatic branch *generation* — F3 records what a cycle chose to log;
  making agents propose alternatives is loop-prompt territory, not engine
  territory.
- No learned models anywhere; prioritization and all verdicts stay
  deterministic.
- No change to gate (`matrix`) semantics: F1 changes only the drill's
  agreement with the gate; F2 lives entirely behind opt-in drill flags.
- No new dependency beyond the Python stdlib + PyYAML.

## Forbidden (negative space)

- Isomorphic variants and reference runs must never be written into a claim's
  `probes/` directory or the ledger — generated state lives only under temp
  directories.
- The drill must never mutate a trap fixture, an iso fixture, or the ledger.
- `recurve trajectories` remains read-only: F3.2 must not cause it to write
  records, and branch data must never be synthesized by the exporter — only
  passed through verbatim.
- An undeclared SKIP must never pass any audit (F1.2 is a floor, not a knob).
