# PRD — eval-optimize: make the oracle path fast, pinned, and spend-safe

> Scope: the work between "mock smoke passes" and "the paid runs are
> trustworthy and tractable" — oracle performance under emulation, oracle
> environment provenance, calibration as a hard pre-spend gate, and the
> first live-API smoke. Everything lands as claims in the `eval` suite,
> RED-first, gated like the rest of the pipeline.
>
> Companion docs: `eval-poc.md` (the experiment this serves),
> `eval-full.md` (the broader program).

## 1 · Why now

Three facts established during oracle bring-up force this wave:

1. **The container tax dominates.** The oracle wrapper does
   `docker run --rm` per grading. Under amd64-on-arm emulation each
   create/start/teardown costs ~1–2s against as little as 0.6s of actual
   test work. The pilot grades ~600 times (200 cells × 3 oracle runs); the
   full run grades ~1,776 times (592 × 3). That is ~15–45 minutes of pure
   container startup — pointless spend of wall-clock and, under
   contention, a threat to timing-derived verdicts.
2. **The oracle environment is real configuration, currently untracked.**
   Verdicts now depend on: image digest (`:latest` is mutable), platform
   emulation (changes timings 2–4×), the wrapper script, timeout policy,
   and an exclusion list that does not exist yet. None of this lands in
   the manifest, the run dir, or the row today. The dataset half of the
   experiment refuses drift; the oracle half must reach the same standard.
3. **Every harness defect found so far biased the same direction.** The
   interpreter bug, the oracle-less rows, the namespace-model mismatch —
   each grades real solutions as *errors*, which read as *oracle
   failures*, which inflate the headline (shipped-bad-work). A broken
   harness "confirms" the thesis. The structural defense is a calibration
   gate that any bug of this class must fail: canonical solutions cannot
   be wrong, so a grading path that errors on them is exposed before a
   cent is spent.

Design rule (standing, restate in `eval/README.md`): **anything that can
change a verdict is pinned and refused-on-drift; anything that can change a
timing is recorded; the manifest stays human-sized because resolution goes
in a lock.**

## 2 · Non-goals

- No native arm64 oracle venv (fallback only if emulation proves unable to
  run required wheels; would be its own claim wave with its own lock).
- No new providers, no SWE-bench, no analysis-layer changes beyond the one
  provenance field named below.
- No relaxation of isolation: grading stays in the container, which stays
  the sandbox; `--network=none` unless calibration proves a task requires
  otherwise (then: documented, pinned exception).

## 3 · Requirements

Each requirement is one-or-more claims: assertion, counterexample (trap),
bounds. IDs are suggestions; the ledger's own numbering wins.

### O1 — Warm oracle container: `docker exec`, not `docker run`

**Assertion.** One persistent container per run (or per grading worker),
started once from the pinned digest; each grading is a `docker exec` into
it. Per-grading container startup cost is eliminated: across a full-run
grading pass, container *starts* ≤ number of grading workers, not number
of gradings.

**Counterexamples (traps).**
- A wrapper that still spawns one container per grading must be caught:
  probe counts container creates during a ≥10-grading batch and fails on
  >workers.
- The warm container dies mid-run → the wrapper must detect, restart from
  the same digest, record the restart in the run log, and re-grade the
  interrupted task — a killed-container fixture must produce a completed,
  correctly-graded batch, not silent errors.
- Digest mismatch: a warm container running any image other than the
  pinned digest must be refused at exec time (retag fixture).

**Bounds.** Same isolation guarantees as `docker run` (fresh workdir per
grading inside the container; no cross-task filesystem reuse; no network).
Wrapper identity changes → new `oracle_env_hash` (O2), so old calibrations
are automatically invalidated rather than silently reused.

### O2 — Oracle environment lock: pin, resolve, refuse

**Assertion.** The manifest gains `[oracle.env]` (intent):
`mode = "docker"`, `image`, `digest` (full sha256 — a bare tag is a
config error), `timeout = "calibrated"`, `exclusions = <path>`. At
`eval plan` time the pipeline writes `oracle.lock.json` into the run dir
(resolution): locally-present image digest, platform + emulation flag,
Python version inside the container, wrapper script hash, resolved
timeout values, exclusion-list content hash, grading concurrency (O4),
and host facts (arch, OS, docker version). Every results row carries
`oracle_env_hash` = digest of the lock.

**Counterexamples (traps).**
- Manifest digest ≠ locally-present image digest → `plan` refuses
  (retagged-image fixture).
- Edited exclusion file without re-lock → content-hash mismatch → refuse.
- A row missing `oracle_env_hash` → schema reject (orchestrator's
  required-keys check extended).

**Bounds.** The lock is machine-written, never hand-edited; the manifest
stays ≤ a screen. Full environment detail lives in the lock; the row
carries only the hash.

### O3 — Calibration as the hard pre-spend gate

**Assertion.** Grading all 148 canonical solutions through the *finished*
oracle path (O1 wrapper, O2 lock) is a claim, and **no paid cell may run
while it is RED**. GREEN means: canonical pass rate is 100% over the
non-excluded set; every exclusion is registered (task id + reason:
emulation casualty, upstream flake, env gap) in an artifact keyed by
`oracle_env_hash`; per-task timings from this run derive the timeout
policy (`max(floor, p99 × k)`, `k` and floor as config knobs); the
calibration artifact (verdicts, timings, derived timeout, exclusions) is
stored keyed by `oracle_env_hash`.

**Counterexamples (traps).**
- A deliberately broken canonical (mutated fixture) must fail calibration
  — proving calibration can fail.
- A calibration artifact whose `oracle_env_hash` does not match the
  current lock must be refused as stale (doctored-artifact fixture).
- The grading-path bug class: a wrapper reintroducing the
  separate-modules namespace error must turn calibration RED (regression
  fixture wired to the historical bug).

**Bounds.** Calibration is sequential by design (clean timings — the
timeout derives from them); one-time cost ~10 min under emulation is
accepted. Exclusions are registered *before* the pilot and frozen for the
paper's run; post-hoc additions require a new calibration and are visible
as a new artifact.

### O4 — Grading concurrency that cannot corrupt verdicts

**Assertion.** Paid-run grading may parallelize (the timeout is already
calibrated; grading timings no longer derive anything), but under a
declared concurrency recorded in the lock, with two protections:
(a) `oracle.grade_concurrency` is a config knob (default conservative);
(b) a grading that *times out* is retried once serially before being
scored — contention-induced slowness must not become an oracle failure.

**Counterexamples (traps).**
- A simulated-contention fixture (task slowed past timeout under load)
  must be scored by the serial retry, not recorded as error.
- Concurrency actually used ≠ concurrency in the lock → refuse.

**Bounds.** Default concurrency low (1–2) for the pilot; raising it for
the full run is a manifest change, visible in the lock. The serial-retry
protection applies to timeouts only, never to genuine test failures.

### O5 — Real-task smoke fixture (mock fidelity)

**Assertion.** The permanent end-to-end smoke uses one real pinned
BigCodeBench-Hard task with its real canonical solution (plus one known-bad
mutant of it), replacing hand-authored fixtures. The smoke exercises the
exact grading convention of the substrate (shared-namespace `task_func`),
so mock-vs-substrate drift is structurally impossible.

**Counterexamples (traps).** The known-bad mutant must grade FAIL (the
smoke can detect a bad solution); a fixture task id absent from the pinned
dataset must be refused.

**Bounds.** One task, hermetic (from the pinned local JSONL), zero API
cost, runs in the standing gate.

### O6 — Live smoke before the pilot (~$1, the only spend this PRD allows)

**Assertion.** One real task × all four cells (2 models × 2 arms) through
the full pipeline with real API calls. GREEN means: telemetry rows carry
real token counts parsed from the agent's output (not estimates); cost
computed against the dated price table matches tokens × price within
rounding; the per-cell token cap demonstrably halts a multi-cycle gated
run *across* cycles (not per cycle); all four rows are analyze-complete
and carry full provenance including `oracle_env_hash`; resume works live
(re-invoking the run performs zero new agent calls).

**Counterexamples (traps).** A mocked usage-report with a missing tokens
field must fail row validation; a cap set below one cycle's spend must
yield a recorded refusal/process outcome, never an unbounded run.

**Bounds.** Spend ceiling for this requirement: ≤ $2. No pilot (n=50) and
no full run (148) until O1–O6 are GREEN.

## 4 · Sequencing

O2 (lock) → O1 (warm wrapper; its hash lands in the lock) → O5 (real-task
smoke against the finished path) → O3 (calibration gate; produces timeout
+ exclusions) → O4 (concurrency policy into the lock) → O6 (live $1
smoke) → *then* the `eval-poc.md` §6 order of operations resumes: pilot
n=50 → full 148.

## 5 · Acceptance for the wave

- Gate GREEN across the `eval` suite including all new claims; every new
  probe has demonstrated RED-first against its trap.
- Full-run grading overhead: container starts ≤ workers (from O1's batch
  probe), versus ~1,776 today.
- A results row sampled from the live smoke re-derives its complete
  oracle environment from `oracle_env_hash` alone.
- Calibration artifact exists, keyed to the current lock, with 100%
  canonical pass over the non-excluded set and every exclusion reasoned.
- Total spend during the wave ≤ $2.
