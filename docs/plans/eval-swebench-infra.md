# PRD — SWE-bench Verified infra: workspace, oracle, calibration, smoke

> Scope: the SWE-bench-specific half of `eval-full.md`'s E2 (`PRD-EVAL-2`).
> This is `eval-optimize.md`'s role, replayed for a genuinely different task
> shape — BigCodeBench-Hard is one function; SWE-bench Verified is a real,
> multi-file repo at a pinned commit. Depends on `eval-arm-kernel.md`'s
> `ArmSpec`/ports (A0/A3 reuse them unchanged, pointed at a new
> `WorkspacePort` adapter) and reuses the dollar-budget + hard-kill watchdog
> (`EV-23`/`EV-24`) as-is — neither is benchmark-specific.
>
> **Ends in a live smoke test** (one instance, 2 models × 2 arms), same
> shape as O6 — the only spend this PRD allows. A statistically powered
> SWE-bench pilot is a later, separately-budgeted phase.

## 1 · Why this isn't just "point BigCodeBench's harness at a new benchmark"

Four real differences force new infrastructure, not new config:

- **The task *is* a repo.** SWE-bench Verified's task shape is `(repo,
  base_commit, problem_statement, test_patch, FAIL_TO_PASS, PASS_TO_PASS,
  environment_setup_commit)` — a real checkout with real dependencies, not
  a file plus a prompt.
- **One oracle image per (repo, version), not one for the whole benchmark.**
  BigCodeBench-Hard shared a single derived container across all 148 tasks.
  SWE-bench spans many distinct projects (django, sympy, astropy, …), each
  needing its own environment — dozens of distinct images across even a
  modest task sample, not one.
- **The agent needs a real dev environment, not just a prompt.** A
  competent agent working a GitHub issue wants to run the repo's own test
  suite while iterating. BigCodeBench's bare-file workspace has nothing
  to run.
- **The held-out oracle (`test_patch` + `FAIL_TO_PASS`/`PASS_TO_PASS`)
  must stay quarantined from a *working* environment, not just an empty
  one.** Harder than BigCodeBench's version of the same principle, because
  the agent's workspace here has to be a fully live, working checkout.

## 2 · Non-goals

- Not the full E2 pilot run (statistically powered, many instances) —
  that's a later, separately-budgeted phase once this smoke passes.
- Not reinventing the dollar-budget/watchdog, `ArmSpec`/ports, or results
  schema — all reused as-is from `eval-optimize.md`/`eval-arm-kernel.md`.
- Not solving image-caching/disk strategy at scale — flagged as a cost
  question for the pilot phase, not solved here.
- Not building A7–A10 for SWE-bench yet — A0/A3 only, matching O6's own
  scope before it was extended.

## 3 · Requirements

### SW1 — Reuse SWE-bench's own instance-building tooling

**Assertion.** The environment image (repo checked out at `base_commit`,
dependencies installed) is built via SWE-bench's own official harness
(`pip install swebench`; their image-building path), pinned by digest —
not a bespoke git-clone-and-pip-install script maintained here.

**Counterexamples (traps).** A locally-hand-rolled materialization that
diverges from the official harness's own instance construction (e.g.
missing an environment-setup step) must be caught by comparing a built
image's test-collection output against the officially-documented one for
a pinned sample instance.

**Bounds.** We own the *pinning and orchestration*, not the *environment
construction* — same "borrow, don't reinvent" rule this whole program has
followed for auths, drill, and the adapter registries.

### SW2 — The agent's workspace is real and working, but oracle-free

**Assertion.** The container the agent works in is built from the
environment image **without** `test_patch` applied — a genuine, working
checkout the agent can run the repo's own (non-hidden) tests against, but
structurally missing the `FAIL_TO_PASS`/`PASS_TO_PASS` tests entirely.
Only the agent's final diff crosses into grading — never the container
itself.

**Counterexamples (traps).** A workspace whose file tree contains any
string from `test_patch` must be refused before an agent ever sees it
(the load-bearing isolation, same principle as BigCodeBench's "workspace
never contains the oracle").

**Bounds.** The agent's container needs network egress for its own model
API calls — same asymmetry already documented for the adversary/governor
ports (isolated from what it shouldn't see, not from the network).

### SW3 — Oracle quarantine: a fresh instance, the diff, and nothing else

**Assertion.** Grading takes the agent's **extracted diff only**, applies
it to a **fresh** copy of the same environment image plus `test_patch`, in
a separate, `--network=none` process — never the agent's own live
container. Mirrors BigCodeBench's quarantine architecture exactly, applied
to SWE-bench's apply-patch-then-test flow instead of a script execution.

**Counterexamples (traps).** A grading pass invoked against the agent's
own container (rather than a fresh one) must be refused — state leakage
from a working session into its own grade is exactly what quarantine
exists to prevent.

**Bounds.** One grading container per (task, arm, model, seed) cell —
never shared across cells, matching BigCodeBench's isolation guarantee.

### SW4 — Calibration against canonical patches, keyed per environment

**Assertion.** Each task's own `patch` field (the real, merged fix) is
applied to a fresh instance, `test_patch` applied, `FAIL_TO_PASS`/
`PASS_TO_PASS` run — 100% pass required over the non-excluded set, exactly
`eval-optimize.md`'s O3 principle, adapted: the calibration artifact and
derived timeout are keyed by **environment-image digest**, not one global
hash, since a task sample can span several distinct environments.

**Counterexamples (traps).** A canonical patch that fails calibration must
be diagnosed and either fixed (environment gap, same as BigCodeBench's
nltk case) or excluded with a registered reason — never silently accepted
as a harness bug.

**Bounds.** Calibration runs once per distinct environment image in the
sample, not once per task — reuse across same-repo-same-version instances.

### SW5 — Warm reuse is per-instance, not per-run

**Assertion.** Unlike BigCodeBench (one shared oracle image, one warm
container for the whole run), SWE-bench's container starts are amortized
**within an instance's own 3 oracle-verification runs** (majority vote),
not across the run's many distinct instances — there is no single
container to keep warm across a heterogeneous task sample.

**Counterexamples (traps).** A grading path that tries to reuse one
instance's warm container for a *different* instance's grading must be
refused (wrong environment, wrong dependencies — silently "passing" would
be worse than an honest error).

**Bounds.** Accept the per-instance container-start cost as real; it's
bounded (3 grades per task, not per-cell-per-task), not eliminated.

### SW6 — The live smoke (the only spend this PRD allows)

**Assertion.** One SWE-bench Verified instance — chosen for a small
environment image, to keep the smoke cheap — run through 2 models × 2
arms (`A0`, `A3`, via `eval-arm-kernel.md`'s `ArmSpec`, unmodified),
reusing the dollar-budget + hard-kill watchdog as-is. Produces four
analyze-complete rows with full provenance (repo, `base_commit`,
environment-image digest) before any pilot-scale spend.

**Counterexamples (traps).** Any of SW1–SW5's traps firing during the
smoke counts as the smoke finding its job, not a failure to hide — same
posture O6 took toward its own budget-cap bug.

**Bounds.** Spend ceiling: ≤ $5. No pilot-scale run (many instances,
statistically powered) until this smoke is clean.

## 4 · Sequencing

`eval-arm-kernel.md`'s `ArmSpec` (dependency, not rebuilt here) → SW1
(environment image via official tooling) → SW2 (agent workspace, oracle-
free) → SW3 (quarantine) → SW4 (calibration, per-environment) → SW5
(per-instance warm reuse) → SW6 (the smoke).

## 5 · Acceptance for the wave

- SW1's environment image is built from SWE-bench's own official tooling,
  digest-pinned, reconciled the same way `eval-optimize.md`'s O2b handles
  the BigCodeBench derived image.
- SW2's isolation trap passes: a workspace containing any `test_patch`
  content is refused before an agent runs.
- SW3's quarantine trap passes: grading against the agent's own live
  container (not a fresh one) is refused.
- SW4's calibration is 100% pass over the non-excluded canonical set for
  every distinct environment image touched by the smoke, with a resolved,
  per-environment timeout.
- SW6's four rows exist, analyze-complete, full provenance, ≤ $5 total
  spend.
- Nothing here changes `ArmSpec`, the dollar-budget/watchdog, or the
  results schema — SWE-bench is a new `WorkspacePort`/oracle adapter pair,
  not a fork of the harness.
