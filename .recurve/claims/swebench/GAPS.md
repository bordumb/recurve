# swebench — SWE-bench Verified infra: workspace, oracle, calibration, smoke

> `docs/plans/eval-swebench-infra.md`: SWE-bench Verified's task shape is a
> real, multi-file repo at a pinned commit, not one function — BigCodeBench's
> oracle infra (`eval-optimize.md`, the `eval` suite) is the direct
> architectural precedent, replayed for that different shape. Depends on
> `eval-arm-kernel.md`'s `ArmSpec`/ports (unmodified: `SWE_A0`/`SWE_A3` are
> new `ArmSpec` instances pointed at a new `WorkspacePort`, not edits to the
> existing `_ARMS` dict) and reuses the dollar-budget + hard-kill watchdog
> (`EV-23`/`EV-24`) as-is.

## Conventions

`missing-surface` claims about `eval/evallib/swebench_env.py`,
`.../swebench_workspace.py`, `.../swebench_quarantine.py`,
`.../swebench_calibration.py`, `.../swebench_warm.py`, `.../swebench_
pipeline.py`, and `.../swebench_taskstore.py`. `reads: none`. Every probe is
hermetic (stdlib + injected fakes — no docker, no network, no spend),
mirroring the `eval`/`armkernel` suites' own convention exactly: the PURE
logic (pinning, reconciliation, quarantine-checking, keying, refusal guards)
is driven directly and is what the gate actually re-runs; the functions that
must touch a real docker daemon or the network are marked `# pragma: no
cover - needs docker[+network]` and exercised only by a real, separately-run
smoke (SW6), never by `recurve matrix --gate`. This is the same split
`oracle_env.py`/`oracle_docker.py`/`oracle_build.py` already use for
BigCodeBench's own oracle image.

## SW-1 — The environment image is built via SWE-bench's OWN instance-building tooling, pinned by digest

The per-instance environment image (repo checked out at `base_commit`,
dependencies installed, `test_patch` NOT applied) is built by calling
straight into `swebench.harness.test_spec.make_test_spec` +
`swebench.harness.docker_build.build_instance_image` — SWE-bench's own
official harness (`pip install swebench`) — never a bespoke git-clone-and-
pip-install script maintained here (`swebench_env.build_environment_image`,
docker-touching, oracle-waived). We own the pin (`environment_image_hash`,
keyed by `instance_id`+`repo`+`base_commit`+the built image's content
digest+platform+host — deliberately excluding the calibration-derived
fields SW4 keys BY this hash) and the reconciliation, not the construction.

The reconciliation itself is pure and hermetic:
`reconcile_test_collection(built_output, official_output)` compares the SET
of collected test node ids between a built environment's `pytest
--collect-only` output and the officially-documented one for a pinned
sample instance (`pallets__flask-5014`) — `"match"` if identical, else
raises `TestCollectionMismatch` naming exactly which tests are missing or
extra. Negative space (guarded by the trap): a reconciliation that accepts a
build missing an environment-setup step (a dependency silently not
installed, so a real test is silently absent from collection) as if it
matched the official construction.

## SW-2 — The agent's workspace is real and working, but structurally oracle-free

`materialize_swe_repo_workspace` (registered as `WorkspacePort
["swe_bench_repo"]` in `materialize.WORKSPACE_PORTS` — one new file, one
registry line, the kernel pipeline itself untouched) starts the agent's
container from SW1's environment image (no `test_patch` — true by
construction, since SWE-bench's own `make_test_spec` never folds it into
`repo_script_list`), extracts that tree onto the host for the agent to edit,
`recurve init`s it, and writes `TASK.md` + `run_tests.sh` (a `docker cp` +
`docker exec` helper so the agent can run the repo's own, non-hidden tests
while iterating — never the hidden FAIL_TO_PASS/PASS_TO_PASS suite, which
does not exist in this container's tree at all).

`assert_quarantined_swe` is the load-bearing guard, run BEFORE the workspace
is ever handed to an agent: `test_patch_signals` pulls the meaningful added
lines out of the instance's `test_patch`, and any of them appearing in any
file the agent can see raises `QuarantineError` (the SAME exception type
BigCodeBench's own `materialize.assert_quarantined` raises — one failure
mode, one name, across both benchmarks). Negative space (guarded by the
trap): a workspace whose container tree contains `test_patch` content,
accepted because the leak check only compared the raw byte-for-byte patch
text (not the per-line signals `test_patch_signals` extracts) and so missed
a leak of the SAME content in reformatted/reindented form.

## SW-3 — Oracle quarantine: a fresh instance, the diff, and nothing else

Grading takes the agent's EXTRACTED DIFF ONLY (`swebench_pipeline.
extract_diff` — a `git diff` against the pre-agent commit
`swebench_workspace.default_extract_tree` seals) and applies it, plus
`test_patch`, to a FRESH container built from the SAME environment image,
`--network=none` for the whole grading process
(`swebench_quarantine.grade_fresh`, docker-touching, oracle-waived) — never
the agent's own live container. `get_eval_report` (SWE-bench's own grading
logic) is reused unchanged, never reimplemented.

`refuse_reuse_of_agent_container` is the pure, hermetic enforcement:
raises `OracleContainerReuseError` if the grading container id equals the
agent's own container id, or if no fresh container id was supplied at all —
`grade_fresh` calls it defensively before a single test runs, so the
invariant is machine-checked in the real path too, not merely true by
construction. Negative space (guarded by the trap): a grading path that
skips this check and proceeds to grade against whatever container id it was
handed, agent's own included.

## SW-4 — Calibration against the canonical patch, keyed per environment image

`calibration.py`'s `derive_calibration`/`calibration_admits_spend`
(`EV-16`-shaped) are reused completely unchanged — this requirement's whole
point is that they are not benchmark-specific.
`run_canonical_patch_calibration` (docker-touching, oracle-waived) applies
`test_patch` + the instance's OWN canonical `patch` to a fresh environment
container, runs FAIL_TO_PASS/PASS_TO_PASS, and feeds the single result into
`derive_calibration` — 100% pass required, exactly the same teeth
BigCodeBench's calibration already has.

What's new, and what this claim actually holds the line on:
`calibration_path_for_environment` keys the calibration artifact by the
FULL `environment_image_hash` (instance identity + image digest), not one
global hash — a SWE-bench task sample spans many distinct environments, so
two different instances' calibrations must never collapse onto the same
file. Negative space (guarded by the trap): a keying function that ignores
part of the identity (e.g. digest only, dropping `instance_id`) so two
DIFFERENT environments' calibrations resolve to the SAME path — silently
grading one instance's task sample under another's timeout/exclusions.

## SW-5 — Warm container reuse is per-instance, not per-run

`PerInstanceWarmRegistry` reuses `warm_oracle.WarmOracle` completely
unchanged (imported, not reimplemented) for exactly the scope that is still
real to amortize: ONE instance's own 3 oracle-verification runs share a
single warm container, started once per instance and torn down (or
replaced) the moment a DIFFERENT instance's grading is requested — there is
no single shared image to keep warm across a heterogeneous task sample, the
way BigCodeBench's one derived oracle image allowed for the whole run.

`grade(instance_id, ...)` is the enforcement: it raises `WrongInstanceError`
rather than ever exec-ing a workload into a container that was warmed for a
DIFFERENT instance — wrong environment, wrong dependencies, and a silent
"pass" under the wrong container would be worse than an honest error.
Negative space (guarded by the trap): a grading path that reuses whatever
container happens to be warm, regardless of which instance it was started
for.

## SW-6 — The live smoke (the only spend this PRD allows)

`swebench_pipeline.py` composes SW1-SW5 into `make_swebench_orchestrator`/
`make_swebench_pipeline_adapter` — a SIBLING to `orchestrate.py`/
`run_pipeline.py`, never a modification of them (the shared kernel pipeline
is untouched; only the oracle-grading call differs, because it must).
`SWE_A0`/`SWE_A3` are new `ArmSpec` instances (both `workspace=
"swe_bench_repo"`, differing only in `done_signal` — `self_report` vs
`gate`, exactly `AK-2`'s A0/A6 insight generalized to a new benchmark) —
`ArmSpec` itself, `DoneSignalPort`, the boundary/audit ports, and the
dollar-budget watchdog are all reused completely unchanged.

This claim's probe is hermetic (a fully-mocked agent + grader drives the
real pipeline functions end to end: `expand_smoke_cells` produces the 2
models x 2 arms x 1 instance cross product, `make_swebench_orchestrator`
seals four analyze-complete rows with full provenance including
`oracle_env_hash`, and `assert_within_budget` enforces the <= $5 ceiling) —
the mechanism is what the gate re-runs forever. The REAL live smoke (one
SWE-bench Verified instance, `pallets__flask-5014` — chosen for its tiny
environment footprint: pure-Python Flask 2.3 deps, 1 FAIL_TO_PASS test, 59
PASS_TO_PASS, a 3-line canonical patch — run through 2 real models x 2 real
arms with real API calls) is a separate, actually-executed invocation whose
`eval/runs/sw6-smoke/results.jsonl` is committed as evidence, exactly the
way `EV-23`/`EV-24` cite the BigCodeBench `O6` live smoke as validating
evidence without themselves re-executing it every gate run. Negative space
(guarded by the trap): a smoke driver that seals a row missing required
provenance, or that keeps running cells past the dollar ceiling instead of
halting.
