# A broken run_isolated that hands the child the PARENT's full, unfiltered
# environment — no scrubbing at all.
import dataclasses
import os
import subprocess


@dataclasses.dataclass(frozen=True)
class IsolatedResult:
    returncode: int
    stdout: str
    stderr: str


def run_isolated(snapshot_root, argv, *, timeout=300, extra_env=None):
    proc = subprocess.run(list(argv), cwd=str(snapshot_root), env=dict(os.environ),
                          capture_output=True, text=True, timeout=timeout)
    return IsolatedResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
