"""runner.py — the resumable work queue over cells.

`run` drives each cell through an adapter and seals exactly one row per cell to
results.jsonl. The resume invariant is load-bearing: cell ids derive from
coordinates, so a re-run reads the sealed ids and skips them — an interrupted
run resumes by doing only what is left, and re-running a completed matrix
invokes the agent zero times. That is what makes a long, expensive run safe to
stop and restart.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def sealed_ids(results_path: str | Path) -> set[str]:
    """The cell ids already written to results.jsonl."""
    p = Path(results_path)
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            ids.add(json.loads(line)["cell_id"])
    return ids


def run(cells: list[dict], results_path: str | Path, adapter,
        workspace_root: str | Path, workers: int = 1) -> int:
    """Run every not-yet-sealed cell through `adapter(cell, workspace)`; append
    each returned row to results.jsonl. Returns the number of cells actually
    invoked (0 on a full resume). Sealing is append-only, so a crash mid-run
    loses at most the in-flight cells, never a sealed one."""
    results_path = Path(results_path)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    ws_root = Path(workspace_root)
    ws_root.mkdir(parents=True, exist_ok=True)
    todo = [c for c in cells if c["cell_id"] not in sealed_ids(results_path)]

    def do(cell: dict) -> dict:
        ws = ws_root / cell["cell_id"]
        row = adapter(cell, ws)
        return {**{k: cell[k] for k in
                   ("cell_id", "model", "arm", "budget", "seed", "task_id")},
                **row}

    rows: list[dict] = []
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(do, todo))
    else:
        rows = [do(c) for c in todo]

    with results_path.open("a") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return len(todo)
