#!/usr/bin/env python3
"""Hermetic, sub-second regression guard for the eval pipeline's orchestrator
sequencing (agent -> boundary -> prepare -> done_signal -> grade).

`eval/src/test_end_to_end_sw6.py` proves the same sequencing against 12 real
cells, real docker oracle grading, and a real `recurve matrix --gate`
subprocess -- genuine end-to-end evidence, but minutes-slow and requires
docker + a real dataset + real per-cell workspaces on disk. This test proves
the SAME two invariants with fakes standing in for docker/the gate CLI, so it
runs in well under a second and needs nothing but a throwaway git repo in a
temp dir. Run: `python3 tests/e2e/test_eval_orchestrator_sequencing.py` from
the repo root.

Both invariants here were real bugs, caught only by actually driving a cell
through the full orchestrator rather than testing each port in isolation:

1. A benchmark whose done-signal artifact (SWE-bench's `solution.py`, a
   diff) must be DERIVED from the workspace needs that derivation to happen
   BEFORE done_signal is consulted, not after grading. `Benchmark.prepare`
   is the seam; test A locks in that `prepare` runs first.
2. SWE-bench's real git checkout lives at `workspace/testbed/`, not the
   workspace root -- a gate check rooted at the wrong directory silently
   checks the wrong repo. Test B locks in that the SWE-bench gate helper
   roots itself there.

Single-cell tests can't catch a THIRD class of bug: cross-cell
contamination or mis-dispatch when several cells run together (the shape
every real matrix actually has -- sw6-smoke itself was 2 models x 2 arms x
3 instances). `test_full_matrix_two_models_two_arms` drives 2 models x
{A0, A9} x 1 task through the REAL `core.runner.run`, not one cell called
directly -- proving per-cell workspace isolation, correct per-arm dispatch
within a single run, resumability, and that `analyze.py` aggregates the
result into the expected 2x2 shape.

Two more real bugs, caught building `cli.py::cmd_run` (the driver that
actually plans -> materializes -> runs a fresh cell, not just replays
already-completed ones) -- both only surfaced by trying to drive it, not
by inspection:

4. `evallib.plan.expand` hardcodes `task["task_id"]` -- exactly right for
   BigCodeBench, but SWE-bench's own tasks key on `instance_id` instead, so
   calling it on a SWE-bench task list raises `KeyError` immediately.
   `test_plan_expand_generalizes_to_swebench_task_id_key` characterizes the
   original bug (still reproducible against the unmodified `evallib`
   function) AND proves `core.plan.expand`'s generalization handles it,
   while staying byte-identical to `evallib.plan.expand`'s own output for
   the BigCodeBench shape it already got right.
5. The generic `WorkspacePort["swe_bench_repo"]` dispatcher
   (`evallib.materialize.materialize`) does not thread a per-instance
   `environment_image_digest` through to `materialize_swe_repo_workspace`
   -- real SWE-bench materialization needs the RIGHT environment image per
   instance, which the generic path silently drops.
   `make_routed_agent` calls `materialize_swe_repo_workspace` directly
   instead (never through the generic dispatcher), threading the cell's
   own lock's digest through by hand.
   `test_routed_agent_threads_environment_digest_to_materialize` proves
   that wiring, with the underlying materialize call faked so no real
   docker/container is needed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECURVE = HERE.parent.parent
EVAL = RECURVE / "eval"
sys.path.insert(0, str(EVAL))

from evallib.arms import arm_spec  # noqa: E402
from src.core.orchestrate import make_orchestrator  # noqa: E402
import src.benchmarks.swebench as swebench_mod  # noqa: E402
from src.benchmarks.swebench import prepare_swe, default_gate_fn  # noqa: E402

PASSED = 0


def ok(label: str, cond: bool, detail: str = ""):
    global PASSED
    if not cond:
        print(f"  FAIL {label}  {detail}")
        raise SystemExit(1)
    PASSED += 1
    print(f"  ok   {label}")


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _build_testbed(workspace: Path, *, fix_text: str = "hello") -> None:
    """Populates `workspace/testbed` in place: a real git repo with one
    committed file, then an uncommitted edit -- exactly the state
    `extract_diff`/`prepare_swe` operate on for real. Takes the target
    workspace directly (rather than allocating its own) so it can be reused
    per-cell inside a matrix, where `core.runner.run` -- not the test --
    decides each cell's own workspace path."""
    testbed = workspace / "testbed"
    testbed.mkdir(parents=True)
    _git(["init", "-q"], testbed)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "config", "commit.gpgsign", "false"], testbed)
    (testbed / "app.py").write_text("def greet():\n    return 'hi'\n")
    _git(["add", "-A"], testbed)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "initial"], testbed)
    (testbed / "app.py").write_text(f"def greet():\n    return '{fix_text}'\n")   # the agent's "fix"


def _make_testbed_workspace(tmp_path: Path) -> Path:
    """Single-cell convenience wrapper over `_build_testbed`, for the tests
    below that only need one cell's workspace."""
    workspace = tmp_path / "cell"
    _build_testbed(workspace)
    return workspace


def _add_wellformed_claim(workspace: Path) -> None:
    """`classify_gated_run`'s `has_wellformed_claim` precondition: at least
    one `probes/*.sh` with a sibling `*.trap/` containing a subdirectory --
    evidence a claim was actually authored, checked BEFORE the gate value
    itself matters. Only needed by the done_signal="gate" test; self_report
    never consults it."""
    probes = workspace / "testbed" / ".recurve" / "claims" / "core" / "probes"
    probes.mkdir(parents=True)
    (probes / "fixture.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (probes / "fixture.sh").chmod(0o755)
    (probes / "fixture.trap" / "counterexample").mkdir(parents=True)


def test_prepare_runs_before_done_signal(tmp_path: Path):
    """The bug: done_signal="self_report" reads workspace/solution.py right
    after the agent terminates. Before the fix, SWE-bench's diff was only
    written during grade() -- called AFTER done_signal -- so declared_done
    was always False for a fresh run. This proves it's True now."""
    workspace = _make_testbed_workspace(tmp_path)
    cell = {"cell_id": "c0", "model": "m", "arm": "A0", "budget": 1, "seed": 0, "task_id": "t0"}
    tasks_by_id = {"t0": {"instance_id": "t0"}}
    solution_seen_by_grade = {}

    def fake_agent(cell, workspace):
        return {"terminated": True}

    def fake_grade_factory():
        def grade(cell, task, workspace):
            solution_seen_by_grade["text"] = Path(workspace, "solution.py").read_text()
            return {"verdict": "pass", "extra_row": {}}
        return grade

    orchestrate = make_orchestrator(
        fake_agent, tasks_by_id, provenance={},
        grade=fake_grade_factory(), prepare=prepare_swe,
    )
    row = orchestrate(cell, workspace)

    ok("declared_done is True (prepare ran before done_signal)", row["declared_done"] is True, row)
    ok("solution.py holds the real diff", "hello" in Path(workspace, "solution.py").read_text())
    ok("grade() saw the SAME diff prepare wrote (no re-extraction)",
       "hello" in solution_seen_by_grade["text"])


def test_gate_helper_roots_at_testbed(tmp_path: Path):
    """The bug: a generic gate check assumes the workspace root IS the git
    checkout -- true for BigCodeBench, false for SWE-bench. This proves
    `default_gate_fn` calls the underlying gate check with `workspace/
    testbed`, not `workspace` -- no docker, no real `recurve` CLI needed,
    just recording what path it was called with."""
    workspace = Path("/some/cell/workspace")
    seen_paths = []

    def fake_gate_verdict(root):
        seen_paths.append(Path(root))
        return "green"

    original = swebench_mod._gate_verdict
    swebench_mod._gate_verdict = fake_gate_verdict
    try:
        verdict = default_gate_fn(workspace)
    finally:
        swebench_mod._gate_verdict = original

    ok("default_gate_fn returns the underlying verdict", verdict == "green")
    ok("gate check was rooted at workspace/testbed, not workspace",
       seen_paths == [workspace / "testbed"], seen_paths)


def test_orchestrator_end_to_end_with_gate_arm(tmp_path: Path):
    """Both fixes together, in the exact shape a real done_signal="gate" SWE
    cell uses: prepare runs first (solution.py exists when grade reads it
    back), and `gate_fn=default_gate_fn` (the REAL, production repointing
    function, unfaked) is what the done-signal port consults -- only the
    underlying `_gate_verdict` call is faked (recording what root it was
    given), so this stays hermetic and fast without needing a real `recurve`
    ledger or subprocess, while still driving the real orchestrator ->
    default_gate_fn wiring end to end."""
    workspace = _make_testbed_workspace(tmp_path)
    _add_wellformed_claim(workspace)
    cell = {"cell_id": "c1", "model": "m", "arm": "A9", "budget": 1, "seed": 0, "task_id": "t0"}
    tasks_by_id = {"t0": {"instance_id": "t0"}}
    seen_paths = []

    def fake_agent(cell, workspace):
        return {"terminated": True}

    def fake_grade(cell, task, workspace):
        return {"verdict": "pass", "extra_row": {}}

    def fake_gate_verdict(root):
        seen_paths.append(Path(root))
        return "green"

    spec = arm_spec("A9")
    ok("A9 really is done_signal=gate (sanity on the fixture itself)", spec.done_signal == "gate")

    original = swebench_mod._gate_verdict
    swebench_mod._gate_verdict = fake_gate_verdict
    try:
        orchestrate = make_orchestrator(
            fake_agent, tasks_by_id, provenance={},
            grade=fake_grade, gate_fn=default_gate_fn, prepare=prepare_swe,
        )
        row = orchestrate(cell, workspace)
    finally:
        swebench_mod._gate_verdict = original

    ok("the real default_gate_fn rooted its check at workspace/testbed",
       seen_paths == [workspace / "testbed"], seen_paths)
    ok("gate=green -> declared_done True", row["declared_done"] is True, row)
    ok("gate_outcome == declared", row["gate_outcome"] == "declared", row)


def test_full_matrix_two_models_two_arms(tmp_path: Path):
    """The shape every real matrix actually has (sw6-smoke itself was 2
    models x 2 arms x 3 instances) -- 2 models x {A0, A9} x 1 task, driven
    TOGETHER through the REAL `core.runner.run`, not one cell called
    directly. Proves: per-cell workspace isolation (each cell's diff is
    distinct; grade() must see the RIGHT one, never a neighbor's),
    correct per-arm dispatch side by side in one run (self_report and gate
    do not bleed into each other), analyze.py aggregates the result into
    the expected 2x2 shape, and a second run against the same
    results_path invokes the agent zero times (the full pipeline's own
    resume contract, not just core/runner.py's isolated guarantee)."""
    from evallib.plan import cell_id as make_cell_id
    from src.core.runner import run as runner_run
    from src.analyze import analyze_rows

    ws_root = tmp_path / "workspaces"
    results_path = tmp_path / "results.jsonl"
    models = ["model-a", "model-b"]
    arms = ["A0", "A9"]
    task_id = "t0"

    cells = [{"cell_id": make_cell_id(model, arm, 1, 0, task_id),
             "model": model, "arm": arm, "budget": 1, "seed": 0, "task_id": task_id}
            for model in models for arm in arms]
    ok("4 distinct cell_ids for 2 models x 2 arms", len({c["cell_id"] for c in cells}) == 4)

    agent_calls = []
    seen_gate_paths = []

    def fake_agent(cell, workspace):
        agent_calls.append(cell["cell_id"])
        # A distinct fix per cell -- proves grade() sees THIS cell's own
        # diff, never a neighbor's (i.e. real workspace isolation, not an
        # accident of running one cell at a time).
        _build_testbed(workspace, fix_text=cell["cell_id"])
        if cell["arm"] == "A9":
            _add_wellformed_claim(workspace)
        return {"terminated": True}

    def fake_grade(cell, task, workspace):
        diff = Path(workspace, "solution.py").read_text()
        ok(f"grade() for {cell['cell_id']} sees its OWN diff, not a neighbor's",
           cell["cell_id"] in diff, diff)
        # model-b always "passes", model-a always "fails" -- gives
        # analyze.py something non-trivial to distinguish per model.
        return {"verdict": "pass" if cell["model"] == "model-b" else "fail", "extra_row": {}}

    def fake_gate_verdict(root):
        seen_gate_paths.append(Path(root))
        return "green"

    tasks_by_id = {task_id: {"instance_id": task_id}}
    original = swebench_mod._gate_verdict
    swebench_mod._gate_verdict = fake_gate_verdict
    try:
        orchestrate = make_orchestrator(
            fake_agent, tasks_by_id, provenance={},
            grade=fake_grade, gate_fn=default_gate_fn, prepare=prepare_swe,
        )
        n = runner_run(cells, results_path, orchestrate, ws_root, workers=1)
    finally:
        swebench_mod._gate_verdict = original

    ok("all 4 cells ran", n == 4, n)
    ok("agent invoked exactly once per cell, never more",
       sorted(agent_calls) == sorted(c["cell_id"] for c in cells), agent_calls)

    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    ok("4 rows sealed", len(rows) == 4, rows)
    by_arm_model = {(r["arm"], r["model"]): r for r in rows}
    ok("all 4 (arm, model) combinations present",
       set(by_arm_model) == {(a, m) for a in arms for m in models}, sorted(by_arm_model))

    for (arm, model), row in by_arm_model.items():
        if arm == "A0":
            ok(f"{arm}/{model}: self_report declared_done True", row["declared_done"] is True, row)
            ok(f"{arm}/{model}: self_report gate_outcome is None", row["gate_outcome"] is None, row)
        else:
            ok(f"{arm}/{model}: gated declared_done True (fake gate green)", row["declared_done"] is True, row)
            ok(f"{arm}/{model}: gated gate_outcome == declared", row["gate_outcome"] == "declared", row)
        expected_verdict = "pass" if model == "model-b" else "fail"
        ok(f"{arm}/{model}: oracle_verdict == {expected_verdict}", row["oracle_verdict"] == expected_verdict, row)

    ok("gate check ran once per A9 cell, each rooted at its OWN testbed",
       len(seen_gate_paths) == 2 and all(p.name == "testbed" for p in seen_gate_paths), seen_gate_paths)

    summary = analyze_rows(rows)
    ok("analyze.py's table has a row for both arms", "| A0 |" in summary and "| A9 |" in summary, summary)
    ok("analyze.py's table has a section for both models",
       "## model-a" in summary and "## model-b" in summary, summary)

    # Resume: re-running the SAME matrix against the SAME results_path must
    # invoke the agent zero times -- the full pipeline's own resume
    # contract, not just core/runner.py's isolated guarantee (which uses a
    # trivial fake adapter, never the real orchestrator).
    agent_calls.clear()
    n2 = runner_run(cells, results_path, orchestrate, ws_root, workers=1)
    ok("resume invokes the agent zero times", n2 == 0 and agent_calls == [], (n2, agent_calls))


def test_plan_expand_generalizes_to_swebench_task_id_key(tmp_path: Path):
    """The bug: `evallib.plan.expand` hardcodes `task["task_id"]` -- exactly
    right for BigCodeBench, but SWE-bench's own tasks key on `instance_id`
    instead, so calling it on a SWE-bench task list raised `KeyError`
    immediately (this is what actually running `cmd_run` against
    sw6-smoke.toml caught -- not code inspection). `core.plan.expand`
    re-does the ONE hardcoded line, parameterized by `task_id_key`, reusing
    `cell_id`/`resolved_gate_config` unchanged."""
    from evallib.plan import expand as old_expand
    from src.core.plan import expand as new_expand

    manifest = {"matrix": {"models": ["m"], "arms": ["A0"], "budgets": [1], "seeds": [0]}}
    swe_tasks = [{"instance_id": "pallets__flask-5014", "instruct_prompt": "fix it"}]

    # Characterizes the original bug: the unmodified evallib function still
    # can't read an instance_id-keyed task list -- if this ever stops
    # raising, evallib.plan.expand itself changed and the rest of this
    # test's premise needs re-checking.
    try:
        old_expand(manifest, swe_tasks)
        raise AssertionError("expected KeyError -- evallib.plan.expand is BigCodeBench-specific")
    except KeyError as e:
        ok("evallib.plan.expand still can't read instance_id-keyed tasks (characterizes the original bug)",
           "task_id" in str(e), e)

    cells = new_expand(manifest, swe_tasks, task_id_key="instance_id")
    ok("core.plan.expand handles instance_id-keyed tasks without raising", len(cells) == 1, cells)
    ok("the resulting cell's task_id coordinate holds the instance_id value",
       cells[0]["task_id"] == "pallets__flask-5014", cells[0])

    # The BigCodeBench shape evallib.plan.expand already got right stays
    # byte-identical -- this is a generalization, not a divergent rewrite.
    bcb_tasks = [{"task_id": "BigCodeBench/1", "instruct_prompt": "do it"}]
    old_cells = old_expand(manifest, bcb_tasks)
    new_cells = new_expand(manifest, bcb_tasks, task_id_key="task_id")
    ok("core.plan.expand is byte-identical to evallib.plan.expand for BigCodeBench's own shape",
       old_cells == new_cells, (old_cells, new_cells))


def test_routed_agent_threads_environment_digest_to_materialize(tmp_path: Path):
    """The bug: the generic `WorkspacePort["swe_bench_repo"]` dispatcher
    (`evallib.materialize.materialize`) does not thread a per-instance
    `environment_image_digest` through to `materialize_swe_repo_workspace`
    -- real SWE-bench materialization needs the RIGHT environment image
    per instance, which the generic path silently drops. `make_routed_agent`
    calls `materialize_swe_repo_workspace` directly instead, threading the
    cell's own lock's digest through by hand. Proven here with the
    underlying materialize call faked (recording what digest it received)
    so no real docker/container is needed."""
    import evallib.swebench_workspace as swebench_workspace_mod
    from src.benchmarks.swebench import make_routed_agent

    seen = {}

    def fake_materialize(dest, task, *, recurve_cmd=None, environment_image_digest=None):
        seen["environment_image_digest"] = environment_image_digest
        seen["task"] = task
        Path(dest, "testbed").mkdir(parents=True, exist_ok=True)
        return Path(dest)

    original = swebench_workspace_mod.materialize_swe_repo_workspace
    swebench_workspace_mod.materialize_swe_repo_workspace = fake_materialize
    try:
        tasks_by_id = {"t0": {"instance_id": "t0"}}
        environment_locks = {"t0": {"digest": "sha256:cafef00d", "environment_image_hash": "eih:x"}}
        agent = make_routed_agent(
            tasks_by_id, environment_locks,
            bare_agent=lambda cell, workspace: {"terminated": True},
        )
        cell = {"cell_id": "c0", "model": "m", "arm": "A0", "budget": 1, "seed": 0, "task_id": "t0"}
        agent(cell, tmp_path / "ws")
    finally:
        swebench_workspace_mod.materialize_swe_repo_workspace = original

    ok("materialize_swe_repo_workspace was called with THIS cell's own environment digest",
       seen.get("environment_image_digest") == "sha256:cafef00d", seen)
    ok("materialize_swe_repo_workspace was called with the real task dict",
       seen.get("task") == {"instance_id": "t0"}, seen)


class _FakeRuntime:
    """A `Runtime`-shaped stub: `adapters/runtime.py::Runtime` has exactly
    `make_adapter`/`make_gated_adapter`, nothing else -- this only needs to
    match that shape, not the real dataclass."""

    def __init__(self):
        self.make_adapter_calls = 0
        self.make_gated_adapter_calls = 0

    def make_adapter(self, prompt_for):
        self.make_adapter_calls += 1
        return lambda cell, workspace: {"terminated": True, "via": "fake-bare"}

    def make_gated_adapter(self, prompt_for, budget):
        self.make_gated_adapter_calls += 1
        return lambda cell, workspace: {"terminated": True, "via": "fake-gated"}


def test_make_routed_agent_uses_the_injected_runtime_not_a_direct_import(tmp_path: Path):
    """A prior version of both `make_routed_agent`s imported
    `evallib.adapters.claude` directly, bypassing `adapters/runtime.py::
    resolve_runtime` entirely -- exactly the indirection that module exists
    to enforce (`resolve_runtime` is the ONE place that should ever import
    the real Claude adapter). Proves a caller-supplied `runtime` is what
    actually gets used, for both benchmarks -- if either one falls back to
    importing `evallib.adapters.claude` directly again, this fake runtime's
    `make_adapter`/`make_gated_adapter` would never be called and the
    resulting agent's `terminated` row would lack the `"via"` marker only
    the fake produces."""
    from src.benchmarks.bigcodebench import make_routed_agent as bcb_routed_agent
    from src.benchmarks.swebench import make_routed_agent as swe_routed_agent

    bcb_runtime = _FakeRuntime()
    bcb_routed_agent({"t0": {"task_id": "t0"}}, None, runtime=bcb_runtime)
    ok("bigcodebench.make_routed_agent constructed its bare agent via the injected runtime",
       bcb_runtime.make_adapter_calls == 1, bcb_runtime.make_adapter_calls)
    ok("bigcodebench.make_routed_agent constructed its gated agent via the injected runtime",
       bcb_runtime.make_gated_adapter_calls == 1, bcb_runtime.make_gated_adapter_calls)

    swe_runtime = _FakeRuntime()
    swe_routed_agent({"t0": {"instance_id": "t0"}}, {"t0": {"digest": "d"}}, runtime=swe_runtime)
    ok("swebench.make_routed_agent constructed its bare agent via the injected runtime",
       swe_runtime.make_adapter_calls == 1, swe_runtime.make_adapter_calls)
    ok("swebench.make_routed_agent constructed its gated agent via the injected runtime",
       swe_runtime.make_gated_adapter_calls == 1, swe_runtime.make_gated_adapter_calls)


def main() -> int:
    import tempfile
    for test in (test_prepare_runs_before_done_signal, test_gate_helper_roots_at_testbed,
                 test_orchestrator_end_to_end_with_gate_arm, test_full_matrix_two_models_two_arms,
                 test_plan_expand_generalizes_to_swebench_task_id_key,
                 test_routed_agent_threads_environment_digest_to_materialize,
                 test_make_routed_agent_uses_the_injected_runtime_not_a_direct_import):
        print(test.__name__)
        with tempfile.TemporaryDirectory() as d:
            test(Path(d))
    print(f"\n{PASSED} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
