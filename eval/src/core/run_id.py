"""run_id.py — a run's identity encoded directly in its directory name.

A run is named `<UTC-timestamp>-<short-git-sha>`, so "when was this, and what
code produced it" is answerable from a directory listing rather than by opening
a results file. The functions here are pure: the caller supplies the current
time and git commit at the boundary, which keeps them trivially testable and
free of any hidden clock or subprocess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

# A run id is exactly a compact UTC timestamp, a dash, and a 7-to-40 char
# lowercase-hex commit. Anything else (the `latest` symlink, a legacy freeform
# directory name) is deliberately not a run id and must be rejected.
_RUN_ID_RE = re.compile(r"^(\d{8}T\d{6}Z)-([0-9a-f]{7,40})$")

_TS_FMT = "%Y%m%dT%H%M%SZ"


@dataclass(frozen=True)
class RunId:
    timestamp: datetime   # timezone-aware, UTC
    git_commit: str        # the commit that produced the run (short or full sha)

    def __str__(self) -> str:
        return f"{self.timestamp.strftime(_TS_FMT)}-{self.git_commit[:7]}"


def new_run_id(now: datetime, git_commit: str) -> RunId:
    """Build a run id from the current time and commit. Any timezone-aware
    `now` is normalized to UTC, so two runs started at the same instant in
    different zones produce the same id."""
    return RunId(timestamp=now.astimezone(timezone.utc), git_commit=git_commit)


def parse_run_id(name: str) -> RunId:
    """Parse a run-directory name back into a `RunId`. Raises `ValueError` for
    anything that is not a run id — the `latest` symlink name, a legacy
    freeform directory, or a commit segment that isn't lowercase hex."""
    m = _RUN_ID_RE.match(name)
    if not m:
        raise ValueError(f"not a run id: {name!r}")
    ts = datetime.strptime(m.group(1), _TS_FMT).replace(tzinfo=timezone.utc)
    return RunId(timestamp=ts, git_commit=m.group(2))
