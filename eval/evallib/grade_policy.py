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

import threading
from contextlib import contextmanager


class ConcurrencyMismatch(RuntimeError):
    """The grading concurrency in use differs from the one recorded in the lock —
    refused, so no run grades under an unaccounted condition."""


def assert_concurrency_matches(used: int, locked: int) -> None:
    if int(used) != int(locked):
        raise ConcurrencyMismatch(
            f"grading concurrency in use ({used}) != the lock's "
            f"grade_concurrency ({locked}) — refusing to grade under a condition "
            f"the calibration did not account for")


class RWLock:
    """A writer-preferring readers-writer lock. Normal gradings hold it in READ
    (shared) mode; a timeout retry takes it in WRITE (exclusive) mode — new
    readers are blocked and in-flight readers are drained first, so the retry runs
    with genuinely zero contention. That exclusivity is what makes the retry
    verdict-independent, which in turn is what lets `grade_concurrency` sit in the
    lock but outside the oracle-env identity."""

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False

    def acquire_read(self) -> None:
        with self._cond:
            while self._writer:          # a pending/active writer blocks new readers
                self._cond.wait()
            self._readers += 1

    def release_read(self) -> None:
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self) -> None:
        with self._cond:
            while self._writer:          # one writer at a time
                self._cond.wait()
            self._writer = True          # set first, so new readers wait
            while self._readers > 0:     # drain in-flight readers
                self._cond.wait()

    def release_write(self) -> None:
        with self._cond:
            self._writer = False
            self._cond.notify_all()

    @contextmanager
    def read(self):
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write(self):
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()


def _default_is_timeout(rc: int, out: str) -> bool:
    # Strict: only the timeout sentinel our runners emit (rc 124). A genuine test
    # failure whose output merely mentions "timeout" is a failure, not a timeout,
    # and must not earn a wasted retry.
    return rc == 124


def serial_retry_on_timeout(grade, rwlock: RWLock, *, is_timeout=None):
    """Wrap a grade backend `grade(workdir, argv, timeout) -> (rc, out)` so a
    timeout — and only a timeout — triggers exactly one retry, and the retry runs
    GENUINELY EXCLUSIVE: the first attempt holds a read lock; on a timeout it is
    released and the retry takes the write lock, draining all in-flight gradings so
    the retry gets a contention-free window. A genuine failure is returned as-is,
    never retried."""
    is_timeout = is_timeout or _default_is_timeout

    def graded(workdir, argv, timeout):
        with rwlock.read():
            rc, out = grade(workdir, argv, timeout)
        if is_timeout(rc, out):
            with rwlock.write():
                rc, out = grade(workdir, argv, timeout)
        return rc, out

    return graded
