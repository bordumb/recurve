"""runner.py — the resumable, crash-resilient work queue over cells.

`run` drives each cell through an adapter and seals its row to results.jsonl
**the moment the cell completes** — appended, flushed, and fsync'd before the
next cell starts. Three resilience properties follow, and they are what make a
long headless run safe:

  - crash mid-run: every cell that finished is already durable on disk, so a
    resume loses at most the cell(s) in flight, never a completed one;
  - one bad cell: an adapter that raises is sealed as a `status: "error"` row
    and the run continues — a single failure never kills the batch;
  - resume: cell ids derive from coordinates, so a re-run skips sealed ids
    (errors included, so a deterministic failure never re-spends) and a
    completed matrix invokes the agent zero times.

`sealed_ids` tolerates a truncated final line (a crash caught mid-write), so
resume never trips over the very partial write a crash left behind.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_COORDS = ("cell_id", "model", "arm", "budget", "seed", "task_id")


def sealed_ids(results_path: str | Path) -> set[str]:
    """The cell ids already durable in results.jsonl. A malformed line — the
    truncated tail a crash can leave mid-write — is skipped, never fatal."""
    p = Path(results_path)
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ids.add(json.loads(line)["cell_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return ids


def run(cells: list[dict], results_path: str | Path, adapter,
        workspace_root: str | Path, workers: int = 1) -> int:
    """Run every not-yet-sealed cell through `adapter(cell, workspace)`, sealing
    each row durably the moment its cell finishes. Returns the number of cells
    invoked this call (0 on a full resume)."""
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
            os.fsync(fh.fileno())   # durable before the next cell starts

    def do(cell: dict) -> None:
        coords = {k: cell[k] for k in _COORDS}
        try:
            row = adapter(cell, ws_root / cell["cell_id"])
        except Exception as e:   # noqa: BLE001 — one bad cell must not kill the run
            seal({**coords, "status": "error", "error": f"{type(e).__name__}: {e}"})
            return
        seal({**coords, **row})

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
