"""Run identity, path layout, per-run audit trail, and per-experiment history.

All hermetic: no real clock, git, or network — callers supply time and commit at
the boundary, so these run anywhere.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core import run_index, run_manager, run_meta, run_paths
from src.core.run_id import new_run_id, parse_run_id


# --- run_id ---------------------------------------------------------------

def test_run_id_str_is_timestamp_dash_short_sha():
    rid = new_run_id(datetime(2026, 7, 6, 3, 22, 10, tzinfo=timezone.utc),
                     "4498221ab0c9deadbeef0011223344556677889a")
    assert str(rid) == "20260706T032210Z-4498221"


def test_run_id_normalizes_a_non_utc_time_to_utc():
    eastern = timezone(timedelta(hours=-4))
    rid = new_run_id(datetime(2026, 7, 6, 0, 0, 0, tzinfo=eastern), "abcdef1234")
    # midnight at UTC-4 is 04:00 UTC
    assert str(rid).startswith("20260706T040000Z-")


def test_run_id_string_round_trips():
    rid = new_run_id(datetime(2026, 7, 6, 3, 22, 10, tzinfo=timezone.utc),
                     "4498221ab0c9deadbeef")
    parsed = parse_run_id(str(rid))
    assert str(parsed) == str(rid)
    assert parsed.git_commit == "4498221"
    assert parsed.timestamp.tzinfo is not None


def test_parse_run_id_rejects_the_latest_symlink_name_and_freeform():
    import pytest
    for bad in ("latest", "o6", "sw6-smoke", "my-run", "20260706T032210Z-nothex"):
        with pytest.raises(ValueError):
            parse_run_id(bad)


def test_parse_run_id_accepts_a_backfilled_commit():
    rid = parse_run_id("20260705T211500Z-397c21e")
    assert rid.git_commit == "397c21e"
    assert rid.timestamp == datetime(2026, 7, 5, 21, 15, 0, tzinfo=timezone.utc)


# --- run_paths ------------------------------------------------------------

def test_run_paths_compose_the_layout():
    root = Path("/x/experiments")
    assert run_paths.experiment_dir(root, "sw6-smoke") == root / "sw6-smoke"
    assert run_paths.manifest_path(root, "sw6-smoke") == root / "sw6-smoke" / "experiment.toml"
    assert run_paths.runs_root(root, "sw6-smoke") == root / "sw6-smoke" / "runs"
    assert run_paths.latest_link(root, "sw6-smoke") == root / "sw6-smoke" / "runs" / "latest"
    assert run_paths.index_path(root, "sw6-smoke") == root / "sw6-smoke" / "runs" / "index.jsonl"


def test_run_dir_uses_the_stringified_run_id():
    root = Path("/x/experiments")
    rid = new_run_id(datetime(2026, 7, 6, 3, 22, 10, tzinfo=timezone.utc), "4498221ff")
    assert run_paths.run_dir(root, "sw6-smoke", rid) == root / "sw6-smoke" / "runs" / str(rid)


# --- run_meta -------------------------------------------------------------

def _sample_meta():
    return run_meta.RunMeta(
        run_id="20260706T032210Z-4498221", created_at="2026-07-06T03:22:10Z",
        git_commit="4498221", adapter_version="0.1.0", manifest_hash="deadbeef",
        command=["eval", "run", "experiments/sw6-smoke/experiment.toml"],
        continuations=[run_meta.Continuation(
            at="2026-07-06T04:00:00Z", git_commit="4498221",
            oracle_env_hash="oeh:abc", requested_sample_n=50, cells_added=12)])


def test_run_meta_write_read_round_trips_every_field(tmp_path):
    p = tmp_path / "run_meta.json"
    meta = _sample_meta()
    run_meta.write(p, meta)
    back = run_meta.read(p)
    assert back == meta
    assert isinstance(back.continuations[0], run_meta.Continuation)


def test_run_meta_write_is_deterministic(tmp_path):
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    run_meta.write(p1, _sample_meta())
    run_meta.write(p2, _sample_meta())
    assert p1.read_text() == p2.read_text()
    assert p1.read_text().endswith("\n")


def test_append_continuation_never_drops_a_prior_entry(tmp_path):
    p = tmp_path / "run_meta.json"
    run_meta.write(p, _sample_meta())   # starts with one continuation
    cont2 = run_meta.Continuation(at="2026-07-07T09:15:00Z", git_commit="7a2f9c1",
                                  oracle_env_hash="oeh:abc", requested_sample_n=100,
                                  cells_added=8)
    meta = run_meta.append_continuation(p, cont2)
    assert len(meta.continuations) == 2
    assert meta.continuations[0].cells_added == 12       # prior entry intact
    assert meta.continuations[1].git_commit == "7a2f9c1"
    assert run_meta.read(p).continuations[1] == cont2     # durable on disk


# --- run_index ------------------------------------------------------------

def test_read_all_is_empty_when_the_index_is_absent(tmp_path):
    assert run_index.read_all(tmp_path / "nope" / "index.jsonl") == []


def test_append_creates_the_index_and_preserves_order(tmp_path):
    idx = tmp_path / "runs" / "index.jsonl"   # parent does not exist yet
    run_index.append(idx, {"run_id": "r1", "cells_added": 12})
    run_index.append(idx, {"run_id": "r2", "cells_added": 8})
    rows = run_index.read_all(idx)
    assert [r["run_id"] for r in rows] == ["r1", "r2"]
    first = idx.read_text().splitlines()[0]
    assert first == json.dumps({"cells_added": 12, "run_id": "r1"}, sort_keys=True)


# --- run_manager: the three-mode lifecycle + drift warning ----------------

def _fresh_meta_with_start(git_commit, oracle_env_hash):
    return run_meta.RunMeta(
        run_id="20260706T032210Z-4498221", created_at="2026-07-06T03:22:10Z",
        git_commit=git_commit, adapter_version="0.1.0", manifest_hash="dead",
        command=["eval", "run"],
        continuations=[run_meta.Continuation(
            at="2026-07-06T03:22:10Z", git_commit=git_commit,
            oracle_env_hash=oracle_env_hash, requested_sample_n=50, cells_added=12)])


def test_no_warning_when_neither_code_nor_oracle_drifts():
    meta = _fresh_meta_with_start("4498221", "oeh:abc")
    assert run_manager.continuation_warnings(meta, "4498221", "oeh:abc") == []


def test_warns_on_code_drift():
    meta = _fresh_meta_with_start("4498221", "oeh:abc")
    warns = run_manager.continuation_warnings(meta, "7a2f9c1", "oeh:abc")
    assert len(warns) == 1
    assert "4498221" in warns[0] and "7a2f9c1" in warns[0]


def test_warns_on_oracle_drift():
    meta = _fresh_meta_with_start("4498221", "oeh:abc")
    warns = run_manager.continuation_warnings(meta, "4498221", "oeh:xyz")
    assert len(warns) == 1
    assert "oeh:abc" in warns[0] and "oeh:xyz" in warns[0]


def test_both_drifts_warn_independently():
    meta = _fresh_meta_with_start("4498221", "oeh:abc")
    assert len(run_manager.continuation_warnings(meta, "7a2f9c1", "oeh:xyz")) == 2


def test_resolve_continue_target_by_latest_and_by_id(tmp_path):
    rid = new_run_id(datetime(2026, 7, 6, 3, 22, 10, tzinfo=timezone.utc), "4498221")
    rd = run_paths.run_dir(tmp_path, "exp", rid)
    rd.mkdir(parents=True)
    run_manager.relink_latest(tmp_path, "exp", str(rid))
    assert run_manager.resolve_continue_target(tmp_path, "exp", "latest") == rd
    assert run_manager.resolve_continue_target(tmp_path, "exp", str(rid)) == rd


def test_resolve_continue_target_missing_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        run_manager.resolve_continue_target(tmp_path, "exp", "20260706T032210Z-4498221")
    with pytest.raises(FileNotFoundError):
        run_manager.resolve_continue_target(tmp_path, "exp", "latest")


def test_relink_latest_repoints_to_the_newest_run(tmp_path):
    for sha, hh in (("aaaaaaa", 1), ("bbbbbbb", 2)):
        rid = new_run_id(datetime(2026, 7, 6, hh, 0, 0, tzinfo=timezone.utc), sha)
        run_paths.run_dir(tmp_path, "exp", rid).mkdir(parents=True)
        run_manager.relink_latest(tmp_path, "exp", str(rid))
    target = run_manager.resolve_continue_target(tmp_path, "exp", "latest")
    assert target.name.endswith("-bbbbbbb")


def test_fresh_run_then_continuation_lifecycle(tmp_path):
    """A fresh managed run records itself as continuation[0]; a later
    continuation appends, and the index carries one line per event."""
    now0 = datetime(2026, 7, 6, 3, 22, 10, tzinfo=timezone.utc)
    run_dir, rid = run_manager.begin_fresh_run(tmp_path, "exp", now0, "4498221")
    assert run_dir.is_dir()
    run_manager.record_fresh(
        run_dir, tmp_path, "exp", rid, now=now0, git_commit="4498221",
        adapter_version="0.1.0", manifest_hash="dead", command=["eval", "run"],
        oracle_env_hash="oeh:abc", sample_n=50, cells_added=12)

    meta = run_meta.read(run_dir / "run_meta.json")
    assert meta.run_id == str(rid)
    assert len(meta.continuations) == 1
    assert run_manager.resolve_continue_target(tmp_path, "exp", "latest") == run_dir
    assert len(run_index.read_all(run_paths.index_path(tmp_path, "exp"))) == 1

    now1 = datetime(2026, 7, 7, 9, 15, 0, tzinfo=timezone.utc)
    run_manager.record_continuation(
        run_dir, tmp_path, "exp", now=now1, git_commit="7a2f9c1",
        oracle_env_hash="oeh:abc", sample_n=100, cells_added=8)
    meta2 = run_meta.read(run_dir / "run_meta.json")
    assert len(meta2.continuations) == 2
    assert meta2.continuations[0].cells_added == 12
    assert len(run_index.read_all(run_paths.index_path(tmp_path, "exp"))) == 2
