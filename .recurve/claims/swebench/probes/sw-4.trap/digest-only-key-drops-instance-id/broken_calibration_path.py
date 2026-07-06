"""The plausible bug: keying the calibration path by the docker image DIGEST
alone, dropping `instance_id`/`base_commit`. Two different instances can
share a base/env image layer (same repo+version) while pinning different
`base_commit`s — a digest-only key would silently collapse their
calibrations onto the same file, one instance's timeout/exclusions grading
another's task sample.
"""

from __future__ import annotations

from pathlib import Path


def calibration_path_for_environment(repo, lock: dict) -> Path:
    return Path(repo) / "eval" / "calibrations" / "swebench" / (lock["digest"].replace(":", "-") + ".json")
