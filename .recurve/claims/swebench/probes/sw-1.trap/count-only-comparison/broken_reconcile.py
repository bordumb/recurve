"""The plausible bug: comparing test-collection COUNT instead of IDENTITY.

A hand-rolled environment build can drop one test and silently pick up a
different one at the same time (e.g. a dependency pin drift changes which
parametrized cases exist) — the total count stays the same, but the actual
set of collected tests has drifted. A reconciliation that only checks
"same number of tests collected" misses this entirely.
"""

from __future__ import annotations

import re


class TestCollectionMismatch(RuntimeError):
    pass


def _count(output: str) -> int:
    for line in output.splitlines():
        m = re.match(r"^(\d+) tests? collected", line.strip())
        if m:
            return int(m.group(1))
    return -1


def reconcile_test_collection(built_output: str, official_output: str) -> str:
    if _count(built_output) == _count(official_output):
        return "match"
    raise TestCollectionMismatch("count mismatch")
