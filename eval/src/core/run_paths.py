"""run_paths.py — where everything lives, computed rather than typed.

Every path in the co-located layout is derived from one experiments root and an
experiment name, so a run directory is never a freeform string a human has to
remember the convention for. Pure path arithmetic: no I/O, no side effects.

    experiments/<name>/
      experiment.toml          the live, human-edited config
      runs/
        <run-id>/              one directory per run
        latest -> <run-id>/   symlink to the most recent run
        index.jsonl           one line per run
"""

from __future__ import annotations

from pathlib import Path


def experiment_dir(experiments_root: Path, name: str) -> Path:
    return experiments_root / name


def manifest_path(experiments_root: Path, name: str) -> Path:
    """The live config for an experiment. Named `experiment.toml` — distinct
    from a run's own frozen `manifest.toml` copy, on purpose."""
    return experiment_dir(experiments_root, name) / "experiment.toml"


def runs_root(experiments_root: Path, name: str) -> Path:
    return experiment_dir(experiments_root, name) / "runs"


def run_dir(experiments_root: Path, name: str, run_id) -> Path:
    return runs_root(experiments_root, name) / str(run_id)


def latest_link(experiments_root: Path, name: str) -> Path:
    return runs_root(experiments_root, name) / "latest"


def index_path(experiments_root: Path, name: str) -> Path:
    return runs_root(experiments_root, name) / "index.jsonl"
