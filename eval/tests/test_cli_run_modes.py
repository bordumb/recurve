"""The three `eval run` modes driven through the real CLI entry point.

Hermetic: `--dry-run` swaps every paid/docker step for a fake port, and
`EXPERIMENTS_ROOT` is redirected into a temp dir so a managed run never touches
the real experiments tree. Requires the gitignored datasets (skips without them).
"""

from __future__ import annotations

import re
import types
from pathlib import Path

import src.cli as cli
from src.core import run_index, run_manager, run_meta, run_paths

EVAL = Path(__file__).resolve().parents[1]


def _args(manifest, *, out=None, cont=None):
    return types.SimpleNamespace(
        manifest=str(manifest), out=out, continue_run=cont,
        dry_run=True, workers=1, keep_workspaces=False)


def _manifest(dir_: Path, name: str, n: int) -> Path:
    txt = (EVAL / "experiments" / "poc-bcb-hard" / "experiment.toml").read_text()
    txt = txt.replace('name = "poc-bcb-hard"', f'name = "{name}"')
    txt = re.sub(r"sample\s*=\s*\{[^}]*\}", f"sample = {{ n = {n}, seed = 7 }}", txt)
    p = dir_ / f"{name}.toml"
    p.write_text(txt)
    return p


def test_fresh_then_continue_grows_the_same_run(tmp_path, monkeypatch, require_datasets):
    monkeypatch.setattr(cli, "EXPERIMENTS_ROOT", tmp_path)

    assert cli.cmd_run(_args(_manifest(tmp_path, "zztest", 2))) == 0
    run_dir = run_manager.resolve_continue_target(tmp_path, "zztest", "latest")
    meta = run_meta.read(run_dir / "run_meta.json")
    assert len(meta.continuations) == 1
    assert meta.continuations[0].cells_added == 8   # 2 tasks x 2 models x 2 arms

    # continue the SAME run with a grown sample -> only the new cells are added
    assert cli.cmd_run(_args(_manifest(tmp_path, "zztest", 4), cont="latest")) == 0
    assert run_manager.resolve_continue_target(tmp_path, "zztest", "latest") == run_dir
    meta2 = run_meta.read(run_dir / "run_meta.json")
    assert len(meta2.continuations) == 2
    assert meta2.continuations[1].cells_added == 8   # the 2 newly-added tasks' cells

    events = [r["event"] for r in run_index.read_all(run_paths.index_path(tmp_path, "zztest"))]
    assert events == ["fresh", "continue"]


def test_continue_a_missing_run_is_refused(tmp_path, monkeypatch, require_datasets):
    monkeypatch.setattr(cli, "EXPERIMENTS_ROOT", tmp_path)
    rc = cli.cmd_run(_args(_manifest(tmp_path, "zznope", 1), cont="latest"))
    assert rc == 2   # no such run to continue -> refused, not silently started


def test_unmanaged_out_leaves_no_audit_trail(tmp_path, monkeypatch, require_datasets):
    monkeypatch.setattr(cli, "EXPERIMENTS_ROOT", tmp_path)
    out = tmp_path / "unmanaged"
    assert cli.cmd_run(_args(_manifest(tmp_path, "zzunmanaged", 1), out=str(out))) == 0
    assert (out / "results.jsonl").exists()
    assert not (out / "run_meta.json").exists()
    assert not (tmp_path / "zzunmanaged").exists()   # no managed experiment dir created
