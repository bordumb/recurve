"""Evidence receipts — code accompanied by its evidence, checkable by someone
who wasn't there.

One receipt per verdict, pinning what ran (probe hash), against what (tree
identity, pinned oracle versions), what it said, and when. Receipts
hash-chain per suite so the trail is tamper-evident; an optional pluggable
signer countersigns each receipt's self-hash. Not "an agent wrote this," but
"here is the re-runnable evidence, and here is the chain proving nobody
edited it after the fact."
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

from .config import Config
from .conformance import Matrix
from .records import RecordError, make_receipt, receipt_hash, validate_receipt


def tree_identity(config: Config) -> tuple[str, str]:
    """git commit when the tree is a repo; otherwise a content digest of the
    tree path's top-level listing + mtimes (weak but honest — it changes when
    the tree does)."""
    tree = config.tree
    if tree is None:
        return ("content", "tree-not-found")
    try:
        r = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return ("git", r.stdout.strip())
    except Exception:
        pass
    h = hashlib.sha256()
    for p in sorted(tree.rglob("*")):
        if ".git" in p.parts:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.relative_to(tree)}:{st.st_size}:{int(st.st_mtime)}\n".encode())
    return ("content", h.hexdigest())


def oracle_versions(config: Config, suite: str) -> dict[str, str]:
    lock = config.suite_for(suite).dir / "harness" / "versions.lock"
    if not lock.exists():
        return {}
    out: dict[str, str] = {}
    for line in lock.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


class ReceiptChain:
    def __init__(self, config: Config, suite: str):
        self.config = config
        self.suite = suite
        self.path = config.state_dir / "receipts" / f"{suite}.jsonl"

    def receipts(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def head(self) -> str | None:
        rs = self.receipts()
        return rs[-1]["self_sha256"] if rs else None

    def append(self, receipt: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(receipt, sort_keys=True) + "\n")

    def verify(self) -> list[str]:
        """Returns problems; empty means the chain holds."""
        problems: list[str] = []
        prev: str | None = None
        for i, r in enumerate(self.receipts()):
            try:
                validate_receipt(r)
            except RecordError as e:
                problems.append(f"{self.suite}[{i}]: {e}")
                continue
            if r["prev"] != prev:
                problems.append(f"{self.suite}[{i}]: chain break — prev={r['prev']!r}, "
                                f"expected {prev!r}")
            prev = r["self_sha256"]
        return problems


def _sign(config: Config, receipt: dict) -> dict:
    if not config.receipts_signer:
        return receipt
    try:
        r = subprocess.run(shlex.split(config.receipts_signer),
                           input=receipt["self_sha256"], capture_output=True,
                           text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            receipt["signature"] = r.stdout.strip()
            receipt["signer"] = config.receipts_signer
    except Exception:
        pass  # an unsigned receipt is still a receipt; signing failures are visible by absence
    return receipt


def emit_for_matrix(config: Config, matrix: Matrix) -> int:
    """Append one receipt per verdict, chained per suite. Returns count."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    kind, value = tree_identity(config)
    chains: dict[str, ReceiptChain] = {}
    oracles: dict[str, dict] = {}
    count = 0
    for r in matrix.results:
        suite = r.gap.suite
        chain = chains.setdefault(suite, ReceiptChain(config, suite))
        oracles.setdefault(suite, oracle_versions(config, suite))
        receipt = make_receipt(
            gap=r.gap.id, suite=suite, verdict=r.outcome.value,
            exit_code=r.exit_code, detail=r.detail[:200],
            probe_path=r.gap.probe, tree_kind=kind, tree_value=value,
            oracle_versions=oracles[suite], observed_at=now, prev=chain.head(),
        )
        chain.append(_sign(config, receipt))
        count += 1
    return count
