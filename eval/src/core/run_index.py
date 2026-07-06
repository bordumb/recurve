"""run_index.py — an experiment's whole history in one appendable file.

`runs/index.jsonl` holds one line per run (fresh or continued), so an
experiment's history is readable with `cat` without opening any run directory.
"""

from __future__ import annotations

import json
from pathlib import Path


def append(index_path: Path, entry: dict) -> None:
    """Append one run's summary line, creating the parent directory if needed.
    Keys are sorted so the line is stable across runs."""
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def read_all(index_path: Path) -> list[dict]:
    """Every run summary in append order. An absent index is an empty history,
    not an error."""
    index_path = Path(index_path)
    if not index_path.exists():
        return []
    return [json.loads(l) for l in index_path.read_text().splitlines() if l.strip()]
