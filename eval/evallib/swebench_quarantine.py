"""swebench_quarantine.py — SW3: a fresh instance, the diff, and nothing else.

Mirrors `quarantine.py`'s architecture (the held-out oracle runs in
isolation, never inside the agent's own process/container) applied to
SWE-bench's apply-patch-then-test flow instead of a script execution.
Grading takes the agent's EXTRACTED DIFF ONLY, applies it to a FRESH copy of
the environment image plus `test_patch`, in a separate `--network=none`
process — never the agent's own live container. `refuse_reuse_of_agent_
container` is the structural guard: state leakage from a working session
into its own grade is exactly what quarantine exists to prevent, so grading
against the agent's own container id is refused before a single test runs.
"""

from __future__ import annotations

import json


class OracleContainerReuseError(RuntimeError):
    """Grading was attempted against the agent's own live container instead
    of a fresh one — refused. Never grade a workspace that graded itself."""


def refuse_reuse_of_agent_container(agent_container_id: str | None,
                                     grading_container_id: str | None) -> None:
    """Raise `OracleContainerReuseError` if grading would run inside the SAME
    container the agent worked in (or if no fresh container was actually
    created — an empty/missing grading id is not "a fresh container", it is
    "no isolation happened"). One grading container per (task, arm, model,
    seed) cell, never shared, never the agent's own — mirrors BigCodeBench's
    isolation guarantee exactly."""
    if not grading_container_id:
        raise OracleContainerReuseError(
            "no fresh grading container id was provided — refusing to grade "
            "without a container to grade IN")
    if agent_container_id and grading_container_id == agent_container_id:
        raise OracleContainerReuseError(
            f"grading container {grading_container_id!r} is the AGENT'S OWN "
            f"container — refusing; state leakage from a working session "
            f"into its own grade is exactly what quarantine prevents")


def build_report_from_log(test_spec, prediction: dict, test_log_path) -> dict:
    """Thin pass-through to SWE-bench's OWN `get_eval_report` — reused, never
    reimplemented (FAIL_TO_PASS/PASS_TO_PASS parsing, resolved-status logic
    all live in the official harness). `prediction` is `{instance_id,
    model_name_or_path, model_patch}` shaped exactly as the harness expects."""
    from swebench.harness.grading import get_eval_report
    return get_eval_report(test_spec=test_spec, prediction=prediction,
                            test_log_path=test_log_path, include_tests_status=True)


def grade_fresh(instance: dict, diff_text: str, environment_image_digest: str, *,
                 agent_container_id: str | None = None, model_name: str = "agent",
                 timeout: int = 1800, client=None, log_dir=None) -> dict:  # pragma: no cover - needs docker
    """Grade `diff_text` (the agent's extracted diff — never its container)
    against a FRESH container built from `environment_image_digest`, with
    `test_patch` applied by SWE-bench's own `eval_script` and
    `--network=none` for the whole grading process. Refuses up front
    (`refuse_reuse_of_agent_container`) if the caller ever passes a grading
    container id equal to the agent's own — defensive, not just structural,
    so the invariant is machine-checked in the real path too, not merely
    "true by construction". Returns `{"resolved": bool, "report": dict,
    "grading_container_id": str}`."""
    import subprocess
    import tempfile
    from pathlib import Path, PurePosixPath
    import docker
    from swebench.harness.constants import (
        DOCKER_PATCH, DOCKER_USER, DOCKER_WORKDIR, KEY_INSTANCE_ID, KEY_MODEL,
        KEY_PREDICTION,
    )
    from swebench.harness.docker_utils import copy_to_container, exec_run_with_timeout, cleanup_container
    from swebench.harness.test_spec.test_spec import make_test_spec

    client = client or docker.from_env()
    test_spec = make_test_spec(instance, namespace=None)
    log_dir = Path(log_dir) if log_dir else Path(tempfile.mkdtemp(prefix="swebench-grade-"))
    log_dir.mkdir(parents=True, exist_ok=True)

    container = client.containers.create(
        image=test_spec.instance_image_key, user=DOCKER_USER, detach=True,
        command="tail -f /dev/null", platform=test_spec.platform,
        network_disabled=True)   # SW3's bound: grading is --network=none, always
    try:
        refuse_reuse_of_agent_container(agent_container_id, container.id)
        container.start()

        patch_file = log_dir / "patch.diff"
        patch_file.write_text(diff_text or "")
        copy_to_container(container, patch_file, PurePosixPath(DOCKER_PATCH))
        applied = False
        for cmd in ("git apply --verbose", "git apply --verbose --reject",
                    "patch --batch --fuzz=5 -p1 -i"):
            r = container.exec_run(f"{cmd} {DOCKER_PATCH}", workdir=DOCKER_WORKDIR, user=DOCKER_USER)
            if r.exit_code == 0:
                applied = True
                break
        if not applied:
            return {"resolved": False, "report": {"patch_successfully_applied": False},
                     "grading_container_id": container.id}

        eval_file = log_dir / "eval.sh"
        eval_file.write_text(test_spec.eval_script)
        copy_to_container(container, eval_file, PurePosixPath("/eval.sh"))
        test_output, timed_out, _ = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
        test_output_path = log_dir / "test_output.txt"
        test_output_path.write_text(test_output)
        if timed_out:
            return {"resolved": False, "report": {"timed_out": True},
                     "grading_container_id": container.id}

        prediction = {KEY_INSTANCE_ID: instance["instance_id"], KEY_MODEL: model_name,
                       KEY_PREDICTION: diff_text}
        report = build_report_from_log(test_spec, prediction, test_output_path)
        resolved = bool(report.get(instance["instance_id"], {}).get("resolved"))
        return {"resolved": resolved, "report": report, "grading_container_id": container.id}
    finally:
        cleanup_container(client, container, None)
