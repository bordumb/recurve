"""swebench_calibration.py — SW4: calibration against the canonical patch,
keyed per environment-image digest.

`calibration.py`'s `derive_calibration`/`calibration_admits_spend` are
reused AS-IS (they are not benchmark-specific — the whole point of this
requirement is that they don't need to be). What's new here is the KEY: a
BigCodeBench run has one oracle env for the whole sample, so one calibration
file suffices; a SWE-bench sample spans many distinct environment images
(one per instance touched), so the calibration artifact and its derived
timeout are keyed by `environment_image_hash` (SW1), not one global hash —
`calibration_path_for_environment` is that keying, and it is the one thing
this module must get right: two DIFFERENT environment images must never
collapse onto the same calibration path (that would silently grade instance
B under instance A's timeout/exclusions — a stale-key bug `calibration_
admits_spend` already refuses given a mismatched hash, but only if the path
lookup itself kept them apart in the first place).
"""

from __future__ import annotations

from pathlib import Path

# Re-exported, not reimplemented — SW4's whole point is that this logic is
# NOT benchmark-specific (docs/plans/eval-swebench-infra.md's own framing).
from evallib.calibration import (  # noqa: F401
    CalibrationError, calibration_admits_spend, derive_calibration, exclusion_content_hash,
)


def calibration_path_for_environment(repo: Path, environment_image_hash: str) -> Path:
    """Where a SWE-bench calibration for this exact environment image lives.
    Keyed by the FULL `environment_image_hash` (which already folds in
    `instance_id` + `base_commit` + image digest, per `swebench_env.
    environment_image_hash`) — so two different instances' environments
    always resolve to two different files, never a collision that would let
    one instance's calibration silently admit spend for another's."""
    return (Path(repo) / "eval" / "calibrations" / "swebench"
            / (environment_image_hash.replace(":", "-") + ".json"))


def run_canonical_patch_calibration(
        instance: dict, environment_image_digest: str, environment_image_hash: str,
        dataset_hash: str, *, registered_exclusions: dict | None = None,
        grader=None, timeout: int = 1800) -> dict:  # pragma: no cover - needs docker
    """Grade the instance's OWN canonical `patch` (never the agent's) through
    the finished oracle path: apply `test_patch` + `patch` to a FRESH
    container from the environment image, run FAIL_TO_PASS/PASS_TO_PASS,
    expect 100% pass (a canonical patch cannot be wrong). Feeds the single
    result into `derive_calibration` keyed by THIS instance's
    `environment_image_hash` — one calibration per environment touched, not
    one per run. `grader` is injectable (the real path calls
    `swebench_quarantine.grade_fresh`); defaults to it lazily so a fully
    mocked call never imports docker."""
    import time
    from evallib.swebench_quarantine import grade_fresh
    grader = grader or grade_fresh

    t0 = time.time()
    try:
        result = grader(instance, instance["patch"], environment_image_digest, timeout=timeout)
        verdict = "pass" if result["resolved"] else "fail"
    except Exception:
        verdict = "error"
    seconds = round(time.time() - t0, 3)

    results = {instance["instance_id"]: {"verdict": verdict, "seconds": seconds}}
    return derive_calibration(environment_image_hash, dataset_hash, results,
                               registered_exclusions or {})
