"""core/runner.py — the same resumable work queue, plus post-seal workspace GC.

Every cell workspace is reproducible from its own sealed row's provenance, so
once a row is durable there is no reason to keep the workspace on disk --
except to debug a specific cell by hand. At benchmark scale (hundreds of
cells, SWE-bench's docker-container-per-cell weight) that unreclaimed
footprint grows without bound. This wraps `evallib.runner.run` unchanged
(same resumability: `sealed_ids`, per-cell fsync, one-bad-cell isolation) and
adds exactly one thing at the seal boundary: tar the workspace, then remove
the directory -- unless `keep_workspaces` says a human wants to inspect it
later.
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evallib.runner import sealed_ids

_COORDS = ("cell_id", "model", "arm", "budget", "seed", "task_id")


def _archive_and_remove(workspace: Path) -> None:
    """Tar `workspace` to a sibling `<cell_id>.tar.gz`, then remove the
    directory tree. A workspace an adapter never created (a cell that errored
    before materializing one) is a silent no-op, not a failure."""
    if not workspace.is_dir():
        return
    archive = workspace.with_suffix(workspace.suffix + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(workspace, arcname=workspace.name)
    shutil.rmtree(workspace)


def run(cells: list[dict], results_path: str | Path, adapter,
       workspace_root: str | Path, workers: int = 1, *,
       keep_workspaces: bool = False) -> int:
    """Byte-for-byte `evallib.runner.run`'s resumability contract (resume
    skips sealed ids, one bad cell seals `status: "error"` and the run
    continues, every seal is fsync'd before the next cell starts) -- plus:
    once a cell's row is durable, its workspace is archived and freed unless
    `keep_workspaces` is set."""
    results_path = Path(results_path)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    ws_root = Path(workspace_root)
    ws_root.mkdir(parents=True, exist_ok=True)
    todo = [c for c in cells if c["cell_id"] not in sealed_ids(results_path)]

    lock = threading.Lock()
    fh = results_path.open("a")

    def seal(row: dict) -> None:
        with lock:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def do(cell: dict) -> None:
        coords = {k: cell[k] for k in _COORDS}
        workspace = ws_root / cell["cell_id"]
        try:
            row = adapter(cell, workspace)
        except Exception as e:   # noqa: BLE001 -- one bad cell must not kill the run
            seal({**coords, "status": "error", "error": f"{type(e).__name__}: {e}"})
        else:
            seal({**coords, **row})
        if not keep_workspaces:
            _archive_and_remove(workspace)

    try:
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(do, todo))
        else:
            for cell in todo:
                do(cell)
    finally:
        fh.close()
    return len(todo)
