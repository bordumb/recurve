"""The plausible bug: a per-instance warm registry that reuses WHATEVER
container is currently warm for `grade()`, regardless of which instance it
was started for — wrong environment, wrong dependencies, and a silent
"pass" under the wrong container would be worse than an honest error.
"""

from __future__ import annotations


class WrongInstanceError(RuntimeError):
    pass


class BrokenWarmRegistry:
    def __init__(self, warm):
        self._warm = warm   # whatever warm container object is currently held

    def grade(self, instance_id, host_workdir, argv, timeout=None):
        # No instance check at all -- always uses whatever is warm.
        return self._warm.grade(host_workdir, argv, timeout=timeout)
