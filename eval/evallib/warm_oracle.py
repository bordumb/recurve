"""warm_oracle.py — one oracle container per run, `docker exec` per grading.

The oracle wrapper's per-grading `docker run --rm` pays a container create/start/
teardown for every grading — ~1-2s under emulation against as little as 0.6s of
work. A full run grades ~1,776 times, so startup alone would burn ~15-45 minutes.
WarmOracle starts ONE container from the pinned digest and execs into it per
grading, so container *starts* are bounded by workers, not gradings.

Correctness is preserved, not traded for speed:
  - the started container's image must equal the pinned digest (retag guard);
  - each grading runs in its own workdir under the shared mount (isolation, no
    cross-task filesystem reuse) with `--network=none` at container start;
  - if the warm container dies mid-run, it is restarted from the same digest (the
    restart recorded) and the interrupted task re-graded — never a silent error.

The docker calls go through an injected `run(cmd) -> (rc, stdout)` so the
orchestration is testable without docker; the default runs real subprocesses.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# docker exec stderr fragments that mean "the container is gone" — restartable.
_DEAD_SIGNALS = ("is not running", "No such container", "not running")


class OracleImageMismatch(RuntimeError):
    """A warm container is running an image other than the pinned digest —
    refused, so grading never runs against a retagged/wrong oracle."""


def _subprocess_runner(cmd: list[str], timeout=None) -> tuple[int, str]:  # pragma: no cover - needs docker
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return p.returncode, (p.stdout + p.stderr)


class WarmOracle:
    """A long-lived oracle container. `start()` once, `grade(workdir, argv)` many
    times, `stop()` at the end (usable as a context manager)."""

    def __init__(self, image_digest: str, shared_base, *,
                 platform: str = "linux/amd64", run=_subprocess_runner):
        self.image_digest = image_digest
        self.base = Path(shared_base)
        self.platform = platform
        self._run = run
        self.cid: str | None = None
        self.starts = 0
        self.restarts = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self) -> None:
        """Start one container from the pinned digest, mounting the shared base,
        network-isolated, kept alive with `sleep infinity`. Refuses if the running
        container's image is not the pinned digest."""
        rc, out = self._run([
            "docker", "run", "-d", "--network=none", "--platform", self.platform,
            "-v", f"{self.base}:/work", "--entrypoint", "sleep",
            self.image_digest, "infinity"])
        self.cid = out.strip()
        self.starts += 1
        self._assert_image()

    def _assert_image(self) -> None:
        rc, out = self._run(["docker", "inspect", "--format", "{{.Image}}", self.cid])
        running = out.strip()
        if running != self.image_digest:
            raise OracleImageMismatch(
                f"warm container {self.cid} runs image {running!r}, pinned is "
                f"{self.image_digest!r} — refusing to grade against a different oracle")

    def _restart(self) -> None:
        self.start()
        self.restarts += 1

    def grade(self, host_workdir, argv: list[str], timeout=None) -> tuple[int, str]:
        """Grade in the warm container. `host_workdir` is a fresh dir under the
        shared base; it is mounted at `/work/<rel>`, and the exec runs there. A
        container death is caught once: restart from the pinned digest, re-grade.
        A timeout is NOT a death (it is a slow test), so it is returned as-is."""
        rel = Path(host_workdir).relative_to(self.base)
        def _exec():
            return self._run(
                ["docker", "exec", "-w", f"/work/{rel}", self.cid, "python", *argv],
                timeout=timeout)
        rc, out = _exec()
        if rc != 0 and any(s in out for s in _DEAD_SIGNALS):
            self._restart()
            rc, out = _exec()
        return rc, out

    def stop(self) -> None:
        if self.cid:
            self._run(["docker", "rm", "-f", self.cid])
            self.cid = None
