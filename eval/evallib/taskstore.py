"""TaskStore — fetch and pin a benchmark to a content hash.

The pin is the whole point: a benchmark that drifts silently makes every
downstream number unreproducible. `content_hash` is a deterministic digest over
the canonical task content; `verify_pin` rejects any dataset that does not match
its recorded pin. The real BigCodeBench-Hard fetch needs `datasets` (optional);
the pinning logic is stdlib-only, so it is testable without the network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# The task fields the pipeline reads. `test` is the HIDDEN oracle — it is pinned
# here (so tampering is detectable) but never materialized into an agent's
# workspace (that quarantine is the materializer's job).
TASK_FIELDS = ("task_id", "instruct_prompt", "test")


def load_jsonl(path: str | Path) -> list[dict]:
    """Load a JSONL task file into a list of dicts, order preserved."""
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _canonical(tasks: list[dict]) -> str:
    """Canonical JSON over the pinned fields only, order-preserving, sorted keys
    — so the hash is stable across formatting but sensitive to any content change."""
    rows = [{k: t.get(k) for k in TASK_FIELDS} for t in tasks]
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(tasks: list[dict]) -> str:
    """SHA-256 over the canonical task content. Deterministic and
    tamper-sensitive: any change to a pinned field changes the digest."""
    return hashlib.sha256(_canonical(tasks).encode()).hexdigest()


def verify_pin(tasks: list[dict], expected_hash: str) -> bool:
    """True iff the tasks hash to the expected pin. A tampered or wrong-revision
    dataset fails here, loudly, before any cell runs against it."""
    return content_hash(tasks) == expected_hash


def load_pinned(source: str | Path, expected_hash: str | None = None,
                expected_count: int | None = None) -> list[dict]:
    """Load tasks from a local JSONL `source` and enforce the pin. Raises
    ValueError on a hash or count mismatch — never returns unpinned data."""
    tasks = load_jsonl(source)
    if expected_count is not None and len(tasks) != expected_count:
        raise ValueError(f"task count {len(tasks)} != pinned {expected_count}")
    if expected_hash is not None and not verify_pin(tasks, expected_hash):
        raise ValueError(f"content hash {content_hash(tasks)} != pinned {expected_hash}")
    return tasks


def fetch_bigcodebench_hard(revision: str, cache_dir: str | Path) -> list[dict]:
    """Fetch bigcode/bigcodebench-hard at a pinned revision and cache it as a
    local JSONL. Requires the optional `datasets` dependency — the only path
    that touches the network, exercised by an actual run, oracle-waived in the
    gate."""
    try:
        from datasets import load_dataset
    except ImportError as e:  # pragma: no cover - exercised only in a real run
        raise RuntimeError(
            "fetching the real benchmark needs the 'run' extra: pip install "
            "'recurve-eval[run]'"
        ) from e
    ds = load_dataset("bigcode/bigcodebench-hard", split="v0.1.0_hf",
                      revision=revision)
    tasks = [{k: r.get(k) for k in ("task_id", "instruct_prompt", "test")} for r in ds]
    cache = Path(cache_dir) / f"bigcodebench-hard@{revision}.jsonl"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
    return tasks
