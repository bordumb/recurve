# eval — the recurve evaluation pipeline, gated

The instrument is held to the standard it measures. The `eval/` pipeline
(docs/plans/eval-poc.md §5) turns an experiment manifest into pinned cells, runs
them through the BYO-agent seam, quarantines a held-out oracle, and analyzes the
results deterministically. Each stage is a claim here.

Design: the pipeline's core logic is stdlib-only, so these probes are hermetic —
they drive the real `evallib` code against fixtures, never the network or a paid
run. The one genuinely external dependency (fetching the real BigCodeBench-Hard
revision from HuggingFace) is an `oracle_waiver`: the probe runs full-strength
where the dataset is reachable and SKIPs (visible, non-blocking debt) where it is
not.

## EV-1 — TaskStore pins the benchmark to a content hash

`taskstore.py` loads a task set and pins it to a deterministic SHA-256 over the
canonical task content; `verify_pin` rejects any dataset that does not match its
recorded pin, and a changed task changes the hash. The pinning logic is
stdlib-only (hermetic); the real BigCodeBench-Hard fetch from HuggingFace needs
the optional `datasets` dependency and is oracle-waived where it is absent.
Negative space (guarded by the trap): a `verify_pin` that accepts a tampered
dataset against its original pin.

## EV-2 — Materializer builds A0/A3 workspaces and quarantines the oracle

`arms.py` maps an arm name to its workspace spec (pure): A0 is the bare task
statement + empty `solution.py`; A3 is the same, `recurve init`-ed.
`materialize.py` builds the git-init'd tmpdir, writing only what the agent may
see — never the hidden `test` field — and `assert_quarantined` refuses any
workspace in which the hidden test text appears. Negative space (guarded by the
trap): a materializer that accepts a workspace containing the hidden oracle.

## EV-3 — Runner: pinned matrix + crash-resilient resumable queue

`plan.expand` turns a manifest and a pinned task set into the full cross product
(task × arm × model × budget × seed) with cell IDs derived from coordinates,
written to `matrix.jsonl` before any agent runs. `runner.run` seals each cell's
row the moment it finishes (append + flush + fsync), which buys the properties a
long headless run needs: a crash mid-run leaves every completed cell durable (a
resume loses only the in-flight cell, not the batch); an adapter that raises is
sealed as a `status: "error"` row and the run continues; a re-run skips sealed
ids (errors included, so a deterministic failure never re-spends) and a completed
matrix invokes the agent zero times; and `sealed_ids` skips a truncated final
line (the partial write a crash leaves), so resume never trips on it. The
adapters and the three CLI verbs complete the surface; gated logic is driven by
mock adapters (no spend). Negative space (guarded by the traps): a runner that
re-invokes sealed cells; a mid-run crash that loses the cells already finished.

## EV-4 — Quarantine evaluator: isolated oracle, 3× majority, tamper-refused

`quarantine.py` runs the hidden unittest suite against the agent's final
`solution.py` in a separate process (a bigcodebench venv in a real run; a clean
subprocess here), never inside the agent's workspace. `oracle_verdict` runs the
suite N times and returns the majority verdict plus the flake rate; `evaluate`
refuses to grade unless the oracle's test text matches the checksum recorded at
fetch time. Negative space (guarded by the trap): grading a solution with a
tampered oracle against the original pin.

## EV-5 — Analysis: deterministic tables from results.jsonl

`analyze.py` is a pure function of the results: same rows in any order produce
byte-identical output. It computes the §4 metrics — per model × arm
shipped-bad-work rate, FDR, ΔFDR, oracle pass rate — with Wilson 95% intervals
and a paired McNemar within each model, all closed-form in stdlib (no scipy, no
notebook state). Negative space (guarded by the trap): an analysis whose output
depends on input row order (non-deterministic).

## EV-6 — Orchestrator: agent → terminal state → oracle → one analyze row

`orchestrate.py` is what a cell does, in the order it must happen: run the
agent, confirm the agent process **terminated** (`SequencingError` refuses to
quarantine a live workspace), read the final `solution.py`, grade it against the
pinned held-out oracle, and seal a row with `declared_done` + `oracle_verdict` +
per-row provenance (dataset revision, model verbatim, recurve commit, adapter
version, seed). For a recurve-gated arm it also records the `terminal_state`
(gate verdict + why the run ended) and the `gate_outcome` from it. The
gated-vs-bare branch keys on the arm's `recurve` **property** (`arm_spec`), not
its name, so a manifest may name a gated arm anything and it still routes right.
`row_is_complete` refuses a run-only row that would leave `analyze` without its
dependent variable. Negative space (guarded by the traps): a declared-only row
accepted as complete; a live workspace quarantined; a differently-named gated
arm routed to the bare path.

## EV-7 — Gated-run outcome classifier: refusal vs process-failure

`classify.py` separates a genuine gate refusal from a harness-operation failure
— the distinction §4/§8.3 insist on, and it cannot be read from the workspace
alone: a red gate is a *refusal* only if the run ended on budget exhaustion,
which is telemetry run-state, not workspace state. `classify_gated_run(workspace,
terminal_state)` reads both. `has_wellformed_claim` checks for a probe with a
kept trap. Boundaries: no claim → `process_failed`; gate BROKEN → `process_failed`
(a probe that can't decide isn't the gate refusing work); gate green → `declared`;
gate red + budget-exhausted → `gate_refused`; gate red + crashed → `process_failed`.
Negative space (a trap per boundary): a no-claim / broken / crashed run
miscredited to the gate as a refusal.

## EV-8 — Telemetry + token-cap enforcement (budget-matched)

`telemetry.parse_usage` extracts token counts from the agent's JSON;
`cost_usd` prices them from the dated table and RAISES on an unpriced model
(never a silent $0); `wall_clock` captures elapsed. Because `claude -p` has no
hard token cap and `recurve run --cap` bounds cycles not tokens, `budget.py`'s
`run_gated_burndown` accumulates a cell's spend across its many cycles against
ONE `TokenBudget` and stops starting cycles once the cap is reached — reporting
the `stop_reason` (gate_green vs budget_exhausted) that EV-6 records and EV-7
classifies from. The cap is **per cell, not per cycle**: the recorded total is
bounded by cap + one cycle's overshoot, never many multiples of it. The gated
Claude adapter drives the real run through it. Negative space (guarded by the
traps): `cost_usd` silently pricing an unknown model at $0; a per-cycle cap that
lets a cell overshoot without bound.

## EV-9 — Figures as data: deterministic, honest, byte-stable

`analyze.figure_specs` is a pure, order-invariant function of the results: the
hero **dumbbell** (baseline→gated shipped-bad per model, Wilson-95% on both
endpoints, Δ, refused count) and the Fig-2 **decomposition** (among
baseline-shipped-bad tasks, what the gated arm did: fixed / refused /
also-shipped-bad / process-failed). Roles are inferred from the data (a gated
arm's rows carry `gate_outcome`), so nothing is baked to an arm name.
`spec_is_honest` encodes two craft rules as guards: the hero x-axis spans the
full [0,1] (never truncated) and a synthetic spec carries a watermark the
renderer stamps onto the image. `render.py` draws them deterministically (fixed
rcParams, no timestamps, the paper's validated palette) to byte-stable SVG+PDF;
`analyze_and_emit` renders them in the same pass as the tables. Negative space
(guarded by the trap): a truncated-axis hero accepted as honest.

## EV-10 — Run pipeline: the conductor `recurve run` actually drives

The stages above are only worth their code if the `run` verb drives them as one.
`run_pipeline.make_pipeline_adapter` is the conductor: it composes the
materializer (EV-2) and the orchestrator (EV-6) into the single adapter the
runner turns, so every cell goes task → fresh quarantined workspace → the
arm-appropriate agent → held-out oracle → one analyze-complete row, with no gap
where `cmd_run` could hand the runner a declared-only row (no `oracle_verdict`)
and burn a paid run for nothing. Two invariants the conductor alone owns: the
agent ALWAYS runs in a materialized workspace (it can read TASK.md before it
writes a line — materialize happens *before* the agent, never after, so it never
clobbers the solution), and the bare/gated agent choice keys on the arm's
`recurve` PROPERTY, not its name — both agents are injectable, so the whole
wiring is gated with mocks and a fully-mocked run never imports the paid agent.
`cli.cmd_run` re-resolves the pinned tasks (with their hidden `test`) from the
frozen manifest, stamps provenance (dataset revision, recurve commit,
adapter version), and drives this adapter — the gated cell's cap read per-cell
from its own budget. Negative space (a trap each): an agent run in a workspace
that was never materialized (blind, no TASK.md); a differently-named gated arm
routed to the bare agent (arm-name coupling).

## EV-11 — The oracle grades in a configurable isolated interpreter

`quarantine.py` promised "a dedicated bigcodebench venv in a real run" but graded
under `sys.executable` — a doc/code gap that would have every real
BigCodeBench-Hard solution mis-graded as an *error*, because those hidden tests
import heavy third-party libraries the eval tooling's own interpreter does not
carry (and cannot be forced to, without colliding with the tooling's deps).
`oracle_python()` closes it: the hidden suite runs under the interpreter named by
`RECURVE_ORACLE_PYTHON` (the operator points it at the BCB venv), falling back to
`sys.executable` when unset — all a hermetic, stdlib-only test needs. The pin
check is upstream of the interpreter, so a tampered oracle is refused no matter
which Python would have graded it. Negative space (guarded by the trap): an
oracle that silently ignores the configured interpreter and grades under
`sys.executable` anyway — the one failure that turns a mis-provisioned venv into
a silent wall of false negatives instead of a loud setup error.

## EV-12 — The oracle grades the substrate's namespace (concatenation)

Every harness defect in this design fails in ONE direction: a correct real
solution graded as an *error*, which reads as an oracle failure, which inflates
shipped-bad-work — the paper's own headline. `sys.executable` (EV-11),
oracle-less rows (EV-10), and this claim are all that failure. BigCodeBench
concatenates the solution and the test into ONE module: the entry point
(`task_func`) is a module global the test references directly — all 148
BCB-Hard tests do this (908 `task_func` references, zero `solution`-module
imports). The oracle graded them as *separate* modules, so the canonical
solution — which cannot be wrong — came back `fail`. `_run_once` now joins
solution + test into a single `oracle_case` module, exactly as the benchmark
intends. The permanent fixture is a REAL pinned BCB-Hard task with its REAL
canonical solution (`fixtures/bcb-hard-854.json` — pure math, deterministic,
stdlib-only), not a hand-authored idealization that could quietly agree with the
harness instead of the substrate; the mock's own `from solution import` fixtures
are exactly how this bug hid through the first smoke. Negative space (the trap):
separate-module grading returning the canonical solution non-`pass`.

## EV-13 — Oracle environment declared and digest-pinned (intent)

The oracle is the untracked half of the experiment: which image graded a
solution can change its verdict, so it is declared in the manifest
(`[oracle.env]`) exactly as the dataset is — and naturalized under the same rule
(*anything that can change a verdict is pinned and refused-on-drift; anything
that can change a timing is recorded; the manifest is intent, the lock is
resolution*). `oracle_env.parse_oracle_env` is the intent half: a docker oracle
MUST carry an immutable `sha256:<64hex>` digest, because a bare `:tag` is mutable
— retag it and two runs grade against different images under the same name with
nothing to show it. A tag or digest smuggled into the `image` field is refused
too, so the `digest` field is the single source of truth; a `local` mode (the
current interpreter) stays available for hermetic tests. Negative space (the
trap): a digest-less bare-tag docker oracle accepted — the mutable-oracle hole.

## EV-14 — Oracle env resolved and locked; refuse-on-drift (resolution)

The resolution half. `resolve_oracle_lock` resolves the validated spec against
the machine into an `oracle.lock.json`: the image digest ACTUALLY present locally
(refused if it disagrees with the manifest, or is absent — the same refusal the
dataset hash gives, so retagging the image and re-running is caught), the
platform + emulation flag, the container's Python version, the grading-wrapper
hash, and a host fingerprint. `oracle_env_hash` digests the verdict-affecting
identity subset ONLY — image digest, platform, network, container Python, wrapper
hash, host — and deliberately excludes the calibration-derived timeout and
exclusion hash, which are keyed BY this hash (including them would be circular).
So any identity change (image, platform, wrapper, python, host — host because
emulation timing lives there) changes the hash and invalidates a stale
calibration automatically, while calibration can still hang its outputs off a
stable key. Negative space (a trap each): a locally-present digest that disagrees
with the manifest accepted (drift not refused); the identity hash ignoring the
grading wrapper (a changed grader reading as the same oracle).

## EV-15 — Every row records which oracle graded it

The oracle-env hash is provenance on par with the dataset revision and recurve
commit: without it, two identical-looking rows could have been graded by
different oracles and nothing would show it. The orchestrator stamps
`oracle_env_hash` from provenance into every row, and `row_is_complete` refuses a
row that lacks it — so "graded by which oracle?" is answerable per row forever, by
dereferencing the hash to the lock in the run dir. The rows stay small (one hash,
not the whole lock). Negative space (the trap): a row without `oracle_env_hash`
accepted as complete — the untraceable-oracle hole.

## EV-16 — Calibration: the gate with teeth (canonical solutions can't be wrong)

The structural defense against the whole bias-toward-headline class. Grade all
148 canonical solutions through the finished oracle path; since a canonical
solution cannot be wrong, any bug that turns correct solutions into errors drops
the pass rate — so no paid cell runs while calibration is RED. The teeth:
`derive_calibration` refuses unless every non-pass canonical is a REGISTERED
exclusion carrying a reason (the pre-authored, frozen table) — an UNEXPLAINED
failure refuses calibration outright, the strongest tooth: a harness bug or an
undocumented exclusion cannot slip through. It also refuses when the non-pass
fraction exceeds a cap even with reasons (a broken harness must not pass by
pre-registering everything), records the exclusion reasons, content-hashes the
registered table (editing a task or a reason later is detectable), and derives
the per-task timeout from the canonical p99 under the real runtime, not guessed.
`calibration_admits_spend` refuses at every boundary — no calibration, a
different oracle env (stale key), a different dataset, an edited exclusion table,
or a pass rate below the bar. Keyed by (oracle_env_hash, dataset_hash), so a
changed oracle or dataset auto-invalidates a stale calibration. Negative space (a
trap each): a stale-key calibration admits spend; an edited table admits spend; a
harness that fails most canonicals calibrates by registering them all; an
unexplained canonical failure calibrates.

## EV-17 — The spend gate is wired into the paid path

EV-16 is the logic; this is the enforcement. `cmd_run` calls
`assert_spend_admitted` FIRST — before it resolves a task or spawns an agent — so
a run whose oracle env has no passing calibration costs exactly nothing.
`assert_spend_admitted` reads the run dir's `oracle.lock.json`, finds the
calibration keyed by its `oracle_env_hash`, and either returns the admitting
calibration (with its resolved timeout, which the run then applies) or refuses; a
real `cmd_run` over an uncalibrated run dir returns non-zero and seals no rows.
`plan` writes the lock (refusing an unresolvable/absent-image oracle), and a
docker run points `RECURVE_ORACLE_PYTHON` at the pinned-image wrapper via the
EV-11 seam. Negative space (the trap): a run admitted, or reaching the work
queue, with no calibration for its oracle env — a paid run on a possibly-broken
oracle.

## EV-18 — The oracle image is derivable-from-repo, reconciled to the pin

A docker rebuild is not bit-reproducible (build-time downloads), so a silently
rebuilt image would quietly become the oracle and bypass the pin → lock →
calibration chain. `eval oracle build` makes the rebuild EXPLICIT: it builds the
derived image from the committed `Dockerfile.nltk` (base BCB image + the nltk
corpora 177/655 need — an environment gap FIXED, not excluded, so those tasks
grade hermetically), with buildx attestations disabled so the Id is
deterministic, then RECONCILES the built Id against the manifest pin —
`reconcile_digest` returns match, or refuses with a remediation that names the
re-pin + recalibrate steps (a different image is a different oracle, its
calibration stale by definition). `plan`'s refusal on an absent image names the
one-command remediation (`eval oracle build`), so a fresh clone reaches
ready-to-plan from committed files alone. Negative space (a trap each): a
divergent rebuild silently adopted; a missing-image refusal that fails to name
the remediation.

## EV-19 — Warm oracle container: one start per run, `docker exec` per grading

The oracle wrapper's per-grading `docker run --rm` pays a container create/start/
teardown for every grading — ~1-2s under emulation against as little as 0.6s of
work; a full run grades ~1,776 times, so startup alone would burn ~15-45 minutes.
`WarmOracle` starts ONE container from the pinned digest and execs into it per
grading, so container *starts* are bounded by workers, not gradings (measured: 1
start for a 10-grading batch, ~0.25s/exec live vs ~1-2s/run). Correctness is kept,
not traded: the started container's image must equal the pinned digest (retag
guard); each grading runs in its own workdir under the shared mount, network-
isolated at container start; and a warm container that dies mid-run is restarted
from the same digest (recorded) and the interrupted task re-graded, never a silent
error. `quarantine` grades through a pluggable backend so the run installs the
warm path while hermetic tests and the docker-run fallback use a fresh subprocess;
the warm grader's source is folded into the oracle-env identity, so switching to
it invalidates a stale calibration. Negative space (a trap each): a grader that
spawns one container per grading; a dead container yielding a silent error instead
of restart+re-grade; an exec into a mismatched-image container.

## EV-20 — The end-to-end smoke fixture is the substrate, not a hand-authored idealization

The first smoke used `from solution import` fixtures, and that is exactly how the
namespace-model bug hid — the mock agreed with the harness instead of the
substrate. So the permanent fixture (`bcb-hard-854.json`) is one REAL pinned
BigCodeBench-Hard task with its real canonical solution and a committed known-bad
mutant, and its fidelity is checked, not assumed: `assert_fixture_faithful`
refuses a fixture whose task id is absent from the pinned dataset, or whose test
has drifted from the dataset's own test for that id (the two ways a fixture could
quietly stop representing the substrate). `grade_fixture` runs the exact
shared-namespace `task_func` convention: the canonical grades PASS, the mutant
grades FAIL, so the smoke can actually detect a bad solution. The byte-match
against the full pinned dataset is oracle-waived where the gitignored dataset is
absent; where present, the fixture's test is verified identical to the substrate's.
Negative space (a trap each): a fixture task absent from the pinned dataset
accepted; the known-bad mutant grading anything but FAIL.

## EV-21 — Calibration honesty: timeout floor + the regression turns it RED

Two properties that keep calibration from being either brittle or vacuous. The
per-task timeout is `max(floor, p99 × k)` (floor and k config knobs), not a bare
`p99 × k` — a suite of trivially-fast canonicals must not yield a knife-edge
timeout that flakes a genuinely slow cell into an *error* (which, being an error,
inflates the headline). And calibration must actually go RED on the grading-path
bug class: the real canonical solution, graded the HISTORICAL wrong way (solution
+ test as separate modules, so the test cannot see `task_func`), comes back
non-pass, and a calibration built from that grading is refused as an unexplained
failure — so a wrapper that reintroduced the namespace bug could never pass
calibration and spend would stay blocked. The correct shared-namespace grading
passes and its calibration is admitted; a deliberately broken canonical also
fails calibration, proving calibration *can* fail. Negative space (a trap each):
a derived timeout that ignores the floor; a separate-modules regression that
calibration fails to catch.
