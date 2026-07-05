"""swebench_warm.py — SW5: warm container reuse is per-instance, not per-run.

BigCodeBench shares ONE oracle image across the whole run, so `warm_oracle.
WarmOracle` keeps one warm container alive for the run's entire lifetime.
SWE-bench has no such shared image — every instance has its own environment
— so there is no single container to keep warm across a heterogeneous task
sample. What IS still true, and still worth amortizing, is that ONE
instance's own 3 oracle-verification runs (majority vote) grade against the
SAME environment image; `PerInstanceWarmRegistry` reuses `WarmOracle`
UNCHANGED (imported, not reimplemented) for exactly that scope — one warm
container per instance, started once per instance and reused across that
instance's own verification runs, torn down (or replaced) the moment a
DIFFERENT instance's grading is requested.

The trap this guards against: a grading path that tries to reuse one
instance's warm container for a different instance's grading — wrong
environment, wrong dependencies, and silently "passing" would be worse than
an honest error. `grade` refuses outright rather than ever exec-ing a
foreign instance's workload into a stale container.
"""

from __future__ import annotations

from evallib.warm_oracle import WarmOracle


class WrongInstanceError(RuntimeError):
    """A grading call named an instance whose warm container is not the one
    currently held — refused, rather than silently grading it in the wrong
    (foreign) environment."""


class PerInstanceWarmRegistry:
    """Holds at most ONE warm container at a time, tagged with the instance
    it belongs to. `warm_for` starts a fresh one when the requested instance
    differs from (or is not yet) the currently-held one — paying the
    per-instance container-start cost as real, not eliminated (SW5's bound):
    3 grades per task, never per-cell-per-task. `grade` is the enforcement:
    it refuses to run ANY instance's workload except the one the currently
    warm container was started for."""

    def __init__(self, *, run=None, platform: str = "linux/amd64"):
        self._run = run
        self._platform = platform
        self._instance_id: str | None = None
        self._image_digest: str | None = None
        self._warm: WarmOracle | None = None
        self.instance_switches = 0

    @property
    def current_instance_id(self) -> str | None:
        return self._instance_id

    def warm_for(self, instance_id: str, image_digest: str, shared_base) -> WarmOracle:
        """Return the warm container for `instance_id`, starting one (and
        stopping any DIFFERENT instance's warm container first) if this is a
        new instance or the digest changed. Reuses the SAME `WarmOracle` for
        repeated calls naming the SAME instance+digest — the amortization
        this requirement exists to keep."""
        if (self._warm is not None and self._instance_id == instance_id
                and self._image_digest == image_digest):
            return self._warm
        if self._warm is not None:
            self._warm.stop()
            self.instance_switches += 1
        kwargs = {"platform": self._platform}
        if self._run is not None:
            kwargs["run"] = self._run
        self._warm = WarmOracle(image_digest, shared_base, **kwargs)
        self._warm.start()
        self._instance_id = instance_id
        self._image_digest = image_digest
        return self._warm

    def grade(self, instance_id: str, host_workdir, argv: list[str], timeout=None):
        """Grade under the currently-warm container — but ONLY if it belongs
        to `instance_id`. Raises `WrongInstanceError` rather than ever
        exec-ing into a foreign instance's stale environment; the caller
        must `warm_for(instance_id, ...)` first (or again, if a different
        instance's grading happened in between)."""
        if self._warm is None or self._instance_id != instance_id:
            raise WrongInstanceError(
                f"no warm container held for instance {instance_id!r} "
                f"(currently warm: {self._instance_id!r}) — refusing to "
                f"grade under a different instance's environment")
        return self._warm.grade(host_workdir, argv, timeout=timeout)

    def stop(self) -> None:
        if self._warm is not None:
            self._warm.stop()
            self._warm = None
            self._instance_id = None
            self._image_digest = None
