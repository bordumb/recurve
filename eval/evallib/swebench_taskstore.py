"""swebench_taskstore.py — SWE-bench Verified instances, pinned to a content hash.

A SWE-bench instance's shape is `(repo, base_commit, problem_statement,
test_patch, patch, FAIL_TO_PASS, PASS_TO_PASS, environment_setup_commit,
version)` — a real repo checkout, not a bare task statement. Every field that
can change the environment built (SW1) or the grading (SW3/SW4) is pinned
here, exactly as `taskstore.py` pins BigCodeBench-Hard: `content_hash` is a
deterministic digest over the canonical instance content, and `verify_pin`
rejects any instance set that does not match its recorded pin. The real
fetch (HuggingFace `princeton-nlp/SWE-bench_Verified`) needs the optional
`datasets` dependency and is oracle-waived where it is absent; the pinning
logic itself is stdlib-only and hermetic.

`test_patch` and `patch` are pinned like every other field — they are the
held-out oracle and the calibration reference respectively, and a tampered
copy of either must be as detectable as a tampered BigCodeBench hidden test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# The instance fields the pipeline reads. `test_patch` is the HIDDEN oracle
# (SW2/SW3's quarantine boundary); `patch` is the canonical fix SW4's
# calibration applies. Both are pinned here (tampering is detectable) but
# `test_patch` is never materialized into an agent's workspace — that
# quarantine is `swebench_workspace.py`'s job.
INSTANCE_FIELDS = (
    "instance_id", "repo", "version", "base_commit", "environment_setup_commit",
    "problem_statement", "test_patch", "patch", "FAIL_TO_PASS", "PASS_TO_PASS",
)


def load_jsonl(path: str | Path) -> list[dict]:
    """Load a JSONL instance file into a list of dicts, order preserved."""
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _normalized(instance: dict) -> dict:
    """FAIL_TO_PASS/PASS_TO_PASS arrive as either a JSON-encoded string or a
    native list depending on source (HF dataset rows serialize them as
    strings; a locally-cached JSONL round-trips them as lists) — normalize to
    a list so the canonical hash is stable across either representation."""
    out = {}
    for k in INSTANCE_FIELDS:
        v = instance.get(k)
        if k in ("FAIL_TO_PASS", "PASS_TO_PASS") and isinstance(v, str):
            v = json.loads(v) if v else []
        out[k] = v
    return out


def _canonical(instances: list[dict]) -> str:
    """Canonical JSON over the pinned fields only, sorted keys, order-preserving
    over the instance list — stable across formatting, sensitive to content."""
    rows = [_normalized(t) for t in instances]
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(instances: list[dict]) -> str:
    """SHA-256 over the canonical instance content. Deterministic and
    tamper-sensitive: any change to a pinned field (including `test_patch` or
    `patch`) changes the digest."""
    return hashlib.sha256(_canonical(instances).encode()).hexdigest()


def verify_pin(instances: list[dict], expected_hash: str) -> bool:
    """True iff the instances hash to the expected pin."""
    return content_hash(instances) == expected_hash


def load_pinned(source: str | Path, expected_hash: str | None = None,
                expected_count: int | None = None) -> list[dict]:
    """Load instances from a local JSONL `source` and enforce the pin. Raises
    ValueError on a hash or count mismatch — never returns unpinned data."""
    instances = load_jsonl(source)
    if expected_count is not None and len(instances) != expected_count:
        raise ValueError(f"instance count {len(instances)} != pinned {expected_count}")
    if expected_hash is not None and not verify_pin(instances, expected_hash):
        raise ValueError(f"content hash {content_hash(instances)} != pinned {expected_hash}")
    return instances


def fetch_swebench_verified(revision: str, cache_dir: str | Path,
                             instance_ids: list[str] | None = None) -> list[dict]:
    """Fetch princeton-nlp/SWE-bench_Verified at a pinned revision and cache it
    as a local JSONL. Requires the optional `datasets` dependency — the only
    path that touches the network, exercised by an actual run, oracle-waived
    in the gate. `instance_ids`, when given, narrows the cached set (the smoke
    only needs one instance, not all 500)."""
    try:
        from datasets import load_dataset
    except ImportError as e:  # pragma: no cover - exercised only in a real run
        raise RuntimeError(
            "fetching the real benchmark needs the 'run' extra: pip install "
            "'recurve-eval[run]'"
        ) from e
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test",
                       revision=revision)
    rows = [{k: r.get(k) for k in INSTANCE_FIELDS} for r in ds]
    if instance_ids:
        wanted = set(instance_ids)
        rows = [r for r in rows if r["instance_id"] in wanted]
    cache = Path(cache_dir) / f"swebench-verified@{revision}.jsonl"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return rows
