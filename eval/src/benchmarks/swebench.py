"""swebench.py — the SWE-bench Verified Benchmark: grading wrapped as a port.

Reuses everything already built and proved via a real, paid smoke run,
completely unchanged: `extract_diff`, `grade_with_majority_vote`,
`swebench_taskstore.load_pinned`, the governor wiring. This module is a thin
adapter — no logic is reimplemented, only relocated behind the grade port so
`swebench_pipeline.py`'s own orchestrator fork is no longer the only way to
run a SWE-bench cell.
"""

from __future__ import annotations

import json
from pathlib import Path

from evallib.swebench_majority import grade_with_majority_vote
from evallib.swebench_pipeline import extract_diff
from evallib.swebench_taskstore import load_pinned

from src.core.benchmark import Benchmark, register
from src.sut.recurve import gate_verdict as _gate_verdict
from src.sut.recurve import make_governed_gate_fn as _make_governed_gate_fn


def prepare_swe(cell: dict, task: dict, workspace) -> None:
    """`Benchmark.prepare` — extracts the agent's diff and writes it to
    `workspace/solution.py` BEFORE `done_signal` is consulted. SWE-bench's
    self-report artifact (the diff) is DERIVED from the workspace, unlike
    BigCodeBench's (the agent writes solution.py itself) -- done_signal=
    "self_report" reads that file immediately after the agent terminates, so
    extraction cannot wait until grading, which runs later."""
    Path(workspace, "solution.py").write_text(extract_diff(Path(workspace)))


def grade_swe(environment_locks: dict):
    """The grade factory: `grade_swe(environment_locks)` returns
    `grade(cell, task, workspace) -> {"verdict", "extra_row"}`.
    `environment_locks[task_id]` is the per-instance environment lock
    (`{digest, environment_image_hash, ...}`) — a genuinely per-instance
    oracle-env shape that must live in `extra_row`, never averaged into the
    shared orchestrator's single `provenance["oracle_env_hash"]` semantics
    BigCodeBench uses. Reads the diff `prepare_swe` already wrote to
    `solution.py` rather than re-extracting it -- one extraction per cell,
    not two."""
    def grade(cell: dict, task: dict, workspace) -> dict:
        workspace = Path(workspace)
        lock = environment_locks[cell["task_id"]]
        diff_text = Path(workspace, "solution.py").read_text()

        agent_container_id = None
        container_json = workspace / "container.json"
        if container_json.exists():
            agent_container_id = json.loads(container_json.read_text()).get("container_id")

        graded = grade_with_majority_vote(task, diff_text, lock["digest"],
                                          agent_container_id=agent_container_id)
        verdict = "pass" if graded["resolved"] else "fail"
        extra_row = {
            "diff": diff_text,
            "oracle_env_hash": lock["environment_image_hash"],
        }
        if "agreement" in graded:
            # Additive-only provenance -- a split vote stays visible, never
            # silently smoothed into `verdict`.
            extra_row["oracle_agreement"] = graded["agreement"]
            extra_row["oracle_unanimous"] = graded["unanimous"]
        return {"verdict": verdict, "extra_row": extra_row}
    return grade


def default_gate_fn(workspace) -> str:
    """`sut.recurve.gate_verdict` assumes the workspace root IS the git
    checkout `recurve matrix --gate` runs in -- true for BigCodeBench, NOT
    for SWE-bench, whose real checkout lives at `workspace/testbed/`
    (`swebench_workspace.materialize_swe_repo_workspace`). Reuses
    `gate_verdict` unchanged, just rooted at the right subdirectory --
    matches `evallib.swebench_pipeline._default_gate` byte-for-byte."""
    return _gate_verdict(Path(workspace) / "testbed")


def make_governed_gate_fn(governor: str, actor_model: str, governor_cmd: str):
    """`sut.recurve.make_governed_gate_fn`, rooted at `workspace/testbed/`
    for the same reason `default_gate_fn` is -- the governor's own gate
    check and its snapshot commit both need the real checkout, not the
    cell's outer workspace directory."""
    inner = _make_governed_gate_fn(governor, actor_model, governor_cmd)

    def gate_fn(workspace):
        return inner(Path(workspace) / "testbed")
    return gate_fn


def _load_tasks(manifest: dict, cache_dir) -> list[dict]:
    t = manifest["tasks"]
    # Manifests store `local` relative to `eval/` -- resolve against
    # `cache_dir`'s own parent rather than depending on the caller's cwd.
    local = Path(cache_dir).parent / t["local"]
    return load_pinned(local, t.get("hash"), t.get("count"))


def resolve_oracle_env(manifest: dict, *, repo=None) -> dict:
    """Per-instance locks, not one shared digest -- the genuinely different
    oracle-env SHAPE this benchmark has (each instance has its own
    environment image). Reads the locks file the manifest's own
    `[oracle.env].locks` names (already built and committed by the real
    smoke run); building missing locks is a separate, explicit step
    (`swebench_env.build_environment_image`), never done silently here."""
    from pathlib import Path
    repo = Path(repo) if repo else Path(__file__).resolve().parents[3]
    locks_rel = manifest.get("oracle", {}).get("env", {}).get("locks")
    if not locks_rel:
        raise KeyError("manifest has no [oracle.env].locks -- per-instance locks must be named")
    path = repo / "eval" / locks_rel
    if not path.exists():
        raise FileNotFoundError(
            f"no locks at {path} -- build them first (swebench_env.build_environment_image "
            f"per instance), then re-run")
    return json.loads(path.read_text())


def calibrate(manifest: dict, repo) -> dict | None:
    """The calibration artifact for ONE instance's environment, if it
    exists on disk -- reuses `swebench_calibration.calibration_path_for_
    environment` completely unchanged. Unlike BigCodeBench's single lock,
    a SWE-bench sample can span several environments, so this takes the
    specific `environment_image_hash` to look up, not the whole manifest."""
    from evallib.swebench_calibration import calibration_path_for_environment
    environment_image_hash = manifest.get("_resolved_environment_image_hash")
    if not environment_image_hash:
        return None
    path = calibration_path_for_environment(repo, environment_image_hash)
    return json.loads(path.read_text()) if path.exists() else None


register(Benchmark(
    name="swebench-verified",
    load_tasks=_load_tasks,
    task_id_key="instance_id",
    grade=grade_swe,
    resolve_oracle_env=resolve_oracle_env,
    calibrate=calibrate,
    prepare=prepare_swe,
))
