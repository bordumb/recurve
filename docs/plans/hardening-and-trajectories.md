# PRD — probe hardening & trajectory export

> Source: the SOTA research behind `docs/papers/recurve-framework.md` (§6.2 and
> §6.1) and `docs/papers/overflow_notes.md` items 1, 2, and 8. The 2025–2026
> record measures two things recurve should answer in code: imperfect checks are
> what trained models learn to exploit (fuzzing found 0.56–0.87 false-positive
> rates on plausible buggy verifiers), and ≥1% contaminated trajectories in
> training data suffice to teach reward hacking. This PRD turns those findings
> into three shipped features. Every behavior is a config/CLI **parameter**, not
> a policy: users tune cost/strictness to their budget.

---

## F1 — Probe fuzzing: measured false-positive rate under generated known-bads

**Purpose.** `recurve drill` today re-proves hand-curated traps. A probe can
pass its one trap and still be leaky. F1 adds an opt-in fuzz pass: per-probe
*generators* emit N generated known-bad variants; the probe must reject every
one; the measured false-positive rate is reported per probe.

**Contract.**

- **F1.1 Generator convention.** A claim may ship an executable
  `probes/<id>.fuzz.sh`. Called with env `FUZZ_OUT=<dir>` and `FUZZ_N=<n>`, it
  writes up to `n` variant fixture directories under `FUZZ_OUT`, each shaped
  exactly like a trap fixture (consumable via `TRAP_FIXTURE`).
  - *Observable:* running the generator with `FUZZ_N=3` produces up to 3
    directories under `FUZZ_OUT`; `recurve drill --fuzz` consumes them.
  - *Counterexample (wrong):* a generator whose output directories are ignored
    by the drill, or a drill that runs generators when `--fuzz` was not given.
  - *Bounded:* only claims that ship a `probes/<id>.fuzz.sh`; others are
    untouched and report nothing.
- **F1.2 FPR measurement and verdict.** `recurve drill --fuzz` runs each
  fuzz-capable closed claim's probe against every generated variant with
  `TRAP_FIXTURE` set. A variant the probe turns GREEN is a **false positive**.
  The drill prints, per probe, `fpr = fp/n`, and exits nonzero iff any probe's
  fpr exceeds the configured threshold.
  - *Observable:* a leaky probe (one that GREENs a generated known-bad) makes
    `recurve drill --fuzz` exit 1 and print that probe's nonzero fpr; a strict
    probe yields `fpr = 0/n` and exit 0.
  - *Counterexample (wrong):* a drill that reports fpr 0 for a probe that
    GREENs a generated known-bad, or that passes overall despite a probe
    exceeding the threshold.
  - *Bounded:* closed claims in the selected suite with a generator present.
- **F1.3 Parameters, not policy.** Fuzzing is **off by default** (zero cost
  unless asked). Knobs: `--fuzz` enables; `[drill] fuzz_n` (default 8) bounds
  variants per probe; `[drill] fuzz_fpr_max` (default 0.0) is the failure
  threshold. CLI flags override config.
  - *Observable:* without `--fuzz` the drill's output and exit code are
    byte-identical to today's; with `fuzz_n = 2` in config, at most 2 variants
    are generated per probe; with `fuzz_fpr_max = 1.0` a leaky probe no longer
    fails the drill (it is reported, not fatal).
  - *Counterexample (wrong):* fuzzing running when not requested; a config
    `fuzz_n` that is ignored.
  - *Bounded:* the `[drill]` config table and the `drill` subcommand surface.

## F2 — Trajectory export: the run-log as a verification-gated dataset

**Purpose.** `.recurve/state/records.jsonl` already stores one record per
cycle. F2 exports it as a training-ready JSONL dataset where every row carries
**reward provenance** — and rows whose reward cannot be re-verified are
excluded by default (the ≥1%-contamination hazard is the motivation).

**Contract.**

- **F2.1 `recurve trajectories` emits one JSON object per cycle record.** Each
  row joins the record with its gap's ledger entry and carries at minimum:
  `gap`, `suite`, `action` (the record's status: closed/parked/failed),
  `attempts`, `reward` (1 for closed, 0 otherwise), `files_touched`,
  `severity`, and a `provenance` object naming the probe path and the number
  of trap fixtures on disk for that gap.
  - *Observable:* on a project with k cycle records, `recurve trajectories`
    writes k (minus excluded) JSON lines with exactly those fields present.
  - *Counterexample (wrong):* a row missing `reward` or `provenance`, or a row
    for a gap that has no cycle record.
  - *Bounded:* records.jsonl × the ledger of the current project.
- **F2.2 Contamination gate.** A row is **verified** iff its gap's probe still
  exists and the gap has at least one non-waived trap fixture on disk. By
  default only verified rows are exported; `--include-unverified` includes the
  rest with `"verified": false` marked on each. A summary line reports counts
  exported vs excluded.
  - *Observable:* a gap with `trap_waiver` set (or no trap dir) is absent from
    default output and present-with-flag under `--include-unverified`.
  - *Counterexample (wrong):* an unverified row exported by default, or
    exported without the `verified: false` mark under the flag.
  - *Bounded:* the export path only; the ledger and records are never mutated.
- **F2.3 Deterministic output.** Rows are emitted in a stable sort (suite,
  gap, run_id, cycle) with sorted JSON keys, so two exports of the same state
  are byte-identical and exports are diffable.
  - *Observable:* running the command twice yields identical bytes.
  - *Counterexample (wrong):* dict-order or set-order leaking into the output
    so consecutive runs differ.
  - *Bounded:* the serializer of this one command.

## F3 — Budget-attached stats: close rates that cannot inflate

**Purpose.** The RLVR measurement critique found headline gains dissolving
under budget-matched evaluation (attempt inflation). recurve's own `stats`
should be constitutionally immune: report close rates **at attempt budgets**,
so a class that closes everything in 1 attempt is distinguishable from one
that closes after 6.

**Contract.**

- **F3.1 `recurve stats` gains budgeted close-rate columns.** Per class, in
  addition to today's raw `close%`, print `close%@1` and `close%@2`: the share
  of cycle records closed with `attempts ≤ 1` (resp. `≤ 2`).
  - *Observable:* on a fixture records set where 2 of 4 gaps closed at 1
    attempt, 1 closed at 3 attempts, 1 parked — stats shows close% 75%,
    close%@1 50%, close%@2 50%.
  - *Counterexample (wrong):* close%@1 equal to raw close% on that fixture
    (i.e. the budget ignored), or budgeted columns exceeding the raw rate.
  - *Bounded:* the `stats` renderer over records.jsonl; no ledger changes.
- **F3.2 Trap-debt line.** `stats` prints the drill-debt summary: how many
  closed gaps carry `trap_waiver` (guards the drill cannot audit), so waived
  verification debt is visible next to the close rates it qualifies.
  - *Observable:* a project with one waived closed gap shows `trap debt: 1
    waived guard` (exact count) in stats output.
  - *Counterexample (wrong):* stats silent about waivers while drill would
    report them.
  - *Bounded:* a read-only count over the ledger.

---

## Non-goals (this PRD)

- No learned models anywhere (prioritization stays deterministic).
- No isomorphic-perturbation *generation* engine — F1 defines the generator
  *contract* and measurement; authoring generators stays per-claim work.
- No changes to gate semantics, probe exit codes, or the ledger schema.
- No network access in any new code path.

## Forbidden (negative space)

- Fuzz variants must never be written into the claim's `probes/` directory or
  the ledger — generated state lives only under a temp `FUZZ_OUT`.
- `recurve trajectories` must never mutate records.jsonl, the ledger, or any
  claim file (read-only command).
- The fuzz pass must never mutate a trap fixture (`fix the probe, never the
  trap` extends to generated evidence).
- No new dependency beyond the Python stdlib + PyYAML (recurve's standing
  constraint).
