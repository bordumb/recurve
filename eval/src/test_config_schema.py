"""test_config_schema.py — manifest validation, dataset registry lookup, and
plan/freeze/replan determinism, proven against the manifests already on
disk, not just synthetic fixtures.

Run: `python3 -m src.test_config_schema` from `eval/` (matches
`test_benchmark_conformance.py`'s own convention).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import src.benchmarks.bigcodebench  # noqa: F401,E402 -- registers on import
import src.benchmarks.swebench  # noqa: F401,E402
from src.core.benchmark import known_names  # noqa: E402
from src.core.dataset_registry import (  # noqa: E402
    DatasetRegistryError, load_registry, resolve_dataset_pin,
)
from src.core.schema import ManifestError, validate_manifest  # noqa: E402

from evallib.plan import expand, write_matrix  # noqa: E402


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def test_real_manifests_validate_clean():
    for name in ("poc-bcb-hard.toml", "sw6-smoke.toml", "o6-smoke.toml"):
        m = _load(EVAL / "experiments" / name)
        validate_manifest(m, known_benchmarks=known_names())  # raises on failure
    print("PASS: real manifests validate clean (poc-bcb-hard, sw6-smoke, o6-smoke)")


def test_unknown_benchmark_fails_precisely():
    m = _load(EVAL / "experiments" / "poc-bcb-hard.toml")
    m["tasks"]["benchmark"] = "not-a-real-benchmark"
    try:
        validate_manifest(m, known_benchmarks=known_names())
        raise AssertionError("expected ManifestError")
    except ManifestError as e:
        assert "not-a-real-benchmark" in str(e), e
        print(f"PASS: unknown benchmark fails precisely -- {e}")


def test_missing_hash_fails_precisely():
    m = _load(EVAL / "experiments" / "poc-bcb-hard.toml")
    del m["tasks"]["hash"]
    try:
        validate_manifest(m, known_benchmarks=known_names())
        raise AssertionError("expected ManifestError")
    except ManifestError as e:
        assert "hash" in str(e), e
        print(f"PASS: missing [tasks].hash fails precisely -- {e}")


def test_ambiguous_budget_fails_precisely():
    """The exact historical shape runs/o6/manifest.toml had before its own
    budget_unit annotation: budgets=[60000], no unit -- defaults to "usd"
    and 60000 trips the sanity bound."""
    m = _load(EVAL / "experiments" / "poc-bcb-hard.toml")
    m["matrix"]["budgets"] = [60000]
    try:
        validate_manifest(m, known_benchmarks=known_names())
        raise AssertionError("expected ManifestError")
    except ManifestError as e:
        assert "60000" in str(e), e
        print(f"PASS: budgets=[60000] with no declared unit fails precisely -- {e}")


def test_historical_o6_manifest_now_declares_tokens():
    m = _load(EVAL / "runs" / "o6" / "manifest.toml")
    validate_manifest(m, known_benchmarks=known_names())  # must NOT raise now
    print("PASS: runs/o6/manifest.toml (budget_unit=tokens, 60000) validates clean")


def test_registry_matches_inline_pin_byte_for_byte():
    registry = load_registry(EVAL / "datasets" / "registry.toml")
    inline = _load(EVAL / "experiments" / "poc-bcb-hard.toml")
    inline_pin = resolve_dataset_pin(inline, registry)
    by_name = resolve_dataset_pin({"tasks": {"dataset": "bigcodebench-hard"}}, registry)
    assert inline_pin == by_name, (inline_pin, by_name)
    print(f"PASS: registry lookup == inline pin, byte-for-byte -- {inline_pin}")

    swe_inline = _load(EVAL / "experiments" / "sw6-smoke.toml")
    swe_pin = resolve_dataset_pin(swe_inline, registry)
    swe_by_name = resolve_dataset_pin({"tasks": {"dataset": "swebench-verified"}}, registry)
    assert swe_pin == swe_by_name, (swe_pin, swe_by_name)
    print(f"PASS: swebench-verified registry lookup == inline pin -- {swe_pin}")


def test_unknown_dataset_name_fails_precisely():
    registry = load_registry(EVAL / "datasets" / "registry.toml")
    try:
        resolve_dataset_pin({"tasks": {"dataset": "not-a-real-dataset"}}, registry)
        raise AssertionError("expected DatasetRegistryError")
    except DatasetRegistryError as e:
        assert "not-a-real-dataset" in str(e), e
        print(f"PASS: unknown dataset name fails precisely -- {e}")


def test_plan_round_trip_is_deterministic(tmp_path=None):
    """manifest -> plan -> frozen manifest.toml -> replan from the frozen
    copy -> identical matrices, byte-for-byte -- proving the schema is
    stable and the freeze-at-plan contract is faithful. Uses
    evallib.plan.expand/write_matrix UNCHANGED (already generic, no
    benchmark hardcoding) against a small real task sample -- no oracle
    resolution, no docker, no API spend."""
    import shutil
    import tempfile

    m = _load(EVAL / "experiments" / "poc-bcb-hard.toml")
    bench = None
    from src.core.benchmark import resolve
    bench = resolve(m["tasks"]["benchmark"])
    tasks = bench.load_tasks(m, EVAL / "datasets")[:3]   # a handful of real tasks

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        run1, run2 = d / "run1", d / "run2"
        run1.mkdir()
        run2.mkdir()

        # plan #1
        (run1 / "manifest.toml").write_text((EVAL / "experiments" / "poc-bcb-hard.toml").read_text())
        cells1 = expand(m, tasks)
        write_matrix(cells1, run1 / "matrix.jsonl")

        # replan from the FROZEN copy, not the original path
        frozen = tomllib.loads((run1 / "manifest.toml").read_text())
        shutil.copy(run1 / "manifest.toml", run2 / "manifest.toml")
        cells2 = expand(frozen, tasks)
        write_matrix(cells2, run2 / "matrix.jsonl")

        m1 = (run1 / "matrix.jsonl").read_text()
        m2 = (run2 / "matrix.jsonl").read_text()
        assert m1 == m2, "replan from the frozen manifest produced a different matrix"
        print(f"PASS: plan -> freeze -> replan is byte-identical ({len(cells1)} cells)")


if __name__ == "__main__":
    test_real_manifests_validate_clean()
    test_unknown_benchmark_fails_precisely()
    test_missing_hash_fails_precisely()
    test_ambiguous_budget_fails_precisely()
    test_historical_o6_manifest_now_declares_tokens()
    test_registry_matches_inline_pin_byte_for_byte()
    test_unknown_dataset_name_fails_precisely()
    test_plan_round_trip_is_deterministic()
    print("\nALL PASS")
