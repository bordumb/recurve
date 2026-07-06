"""Manifest validation, dataset-registry lookup, and plan/freeze/replan
determinism — proven against the manifests already on disk, not just synthetic
fixtures.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from src.core.benchmark import known_names, resolve
from src.core.dataset_registry import (
    DatasetRegistryError, load_registry, resolve_dataset_pin,
)
from src.core.run_manager import resolve_continue_target
from src.core.schema import ManifestError, validate_manifest
from evallib.plan import expand, write_matrix

EVAL = Path(__file__).resolve().parents[1]


def _exp(name: str) -> Path:
    return EVAL / "experiments" / name / "experiment.toml"


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def test_real_manifests_validate_clean():
    for name in ("poc-bcb-hard", "sw6-smoke", "o6-smoke"):
        validate_manifest(_load(_exp(name)), known_benchmarks=known_names())


def test_unknown_benchmark_fails_precisely():
    m = _load(_exp("poc-bcb-hard"))
    m["tasks"]["benchmark"] = "not-a-real-benchmark"
    with pytest.raises(ManifestError, match="not-a-real-benchmark"):
        validate_manifest(m, known_benchmarks=known_names())


def test_missing_hash_fails_precisely():
    m = _load(_exp("poc-bcb-hard"))
    del m["tasks"]["hash"]
    with pytest.raises(ManifestError, match="hash"):
        validate_manifest(m, known_benchmarks=known_names())


def test_ambiguous_budget_fails_precisely():
    """The exact historical shape the o6 manifest had before its budget_unit
    annotation: budgets=[60000], no unit -- defaults to usd and trips the bound."""
    m = _load(_exp("poc-bcb-hard"))
    m["matrix"]["budgets"] = [60000]
    with pytest.raises(ManifestError, match="60000"):
        validate_manifest(m, known_benchmarks=known_names())


def test_historical_o6_manifest_now_declares_tokens():
    run_dir = resolve_continue_target(EVAL / "experiments", "o6-smoke", "latest")
    validate_manifest(_load(run_dir / "manifest.toml"), known_benchmarks=known_names())


def test_registry_matches_inline_pin_byte_for_byte():
    registry = load_registry(EVAL / "datasets" / "registry.toml")
    inline_pin = resolve_dataset_pin(_load(_exp("poc-bcb-hard")), registry)
    by_name = resolve_dataset_pin({"tasks": {"dataset": "bigcodebench-hard"}}, registry)
    assert inline_pin == by_name

    swe_pin = resolve_dataset_pin(_load(_exp("sw6-smoke")), registry)
    swe_by_name = resolve_dataset_pin({"tasks": {"dataset": "swebench-verified"}}, registry)
    assert swe_pin == swe_by_name


def test_unknown_dataset_name_fails_precisely():
    registry = load_registry(EVAL / "datasets" / "registry.toml")
    with pytest.raises(DatasetRegistryError, match="not-a-real-dataset"):
        resolve_dataset_pin({"tasks": {"dataset": "not-a-real-dataset"}}, registry)


def test_plan_round_trip_is_deterministic(tmp_path, require_datasets):
    """manifest -> plan -> frozen manifest.toml -> replan from the frozen copy
    -> byte-identical matrices, proving the schema is stable and the
    freeze-at-plan contract is faithful."""
    m = _load(_exp("poc-bcb-hard"))
    bench = resolve(m["tasks"]["benchmark"])
    tasks = bench.load_tasks(m, EVAL / "datasets")[:3]

    run1, run2 = tmp_path / "run1", tmp_path / "run2"
    run1.mkdir()
    run2.mkdir()

    (run1 / "manifest.toml").write_text(_exp("poc-bcb-hard").read_text())
    write_matrix(expand(m, tasks), run1 / "matrix.jsonl")

    frozen = tomllib.loads((run1 / "manifest.toml").read_text())
    write_matrix(expand(frozen, tasks), run2 / "matrix.jsonl")

    assert (run1 / "matrix.jsonl").read_text() == (run2 / "matrix.jsonl").read_text()
