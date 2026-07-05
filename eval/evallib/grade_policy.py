"""grade_policy.py — parallel grading that cannot corrupt a verdict.

Once the timeout is calibrated, grading timings no longer derive anything, so the
paid run may grade cells in parallel — but under a concurrency DECLARED in the
lock, with two protections so speed never turns into a false verdict:

  - a grading that TIMES OUT is retried once SERIALLY before it is scored, so a
    contention-slowed (but valid) grade gets one contention-free attempt instead
    of being misrecorded as an oracle error (an error, like every harness defect
    here, inflates the shipped-bad-work headline);
  - the concurrency actually used must equal the concurrency in the lock, else
    the run refuses — it cannot silently grade under a condition the calibration
    did not account for.

The serial retry fires on a TIMEOUT only, never on a genuine test failure, and is
bounded to exactly one retry.
"""

from __future__ import annotations


class ConcurrencyMismatch(RuntimeError):
    """The grading concurrency in use differs from the one recorded in the lock —
    refused, so no run grades under an unaccounted condition."""


def assert_concurrency_matches(used: int, locked: int) -> None:
    if int(used) != int(locked):
        raise ConcurrencyMismatch(
            f"grading concurrency in use ({used}) != the lock's "
            f"grade_concurrency ({locked}) — refusing to grade under a condition "
            f"the calibration did not account for")


def _default_is_timeout(rc: int, out: str) -> bool:
    return rc == 124 or "TIMEOUT" in (out or "")


def serial_retry_on_timeout(grade, serial_lock, *, is_timeout=None):
    """Wrap a grade backend `grade(workdir, argv, timeout) -> (rc, out)` so a
    timeout — and only a timeout — triggers exactly one retry, run while holding
    `serial_lock` (retries do not pile on each other, giving the retry a calmer,
    contention-free window). A genuine failure is returned as-is, never retried."""
    is_timeout = is_timeout or _default_is_timeout

    def graded(workdir, argv, timeout):
        rc, out = grade(workdir, argv, timeout)
        if is_timeout(rc, out):
            with serial_lock:
                rc, out = grade(workdir, argv, timeout)
        return rc, out

    return graded
