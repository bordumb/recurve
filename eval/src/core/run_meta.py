"""run_meta.py — the audit trail a run carries about itself.

`run_meta.json` records which code produced a run, when it started, the exact
command that launched it, and — as a run is grown over several sittings — every
later continuation's own code version and coverage delta. This is what makes it
visible when a single run directory ends up holding cells graded under two
different commits or two different oracle environments.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Continuation:
    at: str                          # ISO-8601 UTC, when this batch was added
    git_commit: str                   # the code that graded this batch
    oracle_env_hash: str | None       # None when the benchmark has no single shared lock
    requested_sample_n: int | None    # the sample size asked for at this continuation
    cells_added: int                  # how many new cells this batch sealed


@dataclass
class RunMeta:
    run_id: str
    created_at: str                   # ISO-8601 UTC
    git_commit: str                    # the commit HEAD when the run started
    adapter_version: str
    manifest_hash: str                 # content hash of the frozen manifest.toml
    command: list[str]                 # argv, for exact reproduction
    continuations: list[Continuation] = field(default_factory=list)


def write(path: Path, meta: RunMeta) -> None:
    """Serialize with sorted keys and a trailing newline, so the file is a
    stable, diffable artifact."""
    Path(path).write_text(json.dumps(asdict(meta), indent=2, sort_keys=True) + "\n")


def read(path: Path) -> RunMeta:
    d = json.loads(Path(path).read_text())
    d["continuations"] = [Continuation(**c) for c in d.get("continuations", [])]
    return RunMeta(**d)


def append_continuation(path: Path, cont: Continuation) -> RunMeta:
    """Add one continuation entry without disturbing the existing ones, and
    persist the result."""
    meta = read(path)
    meta.continuations.append(cont)
    write(path, meta)
    return meta
