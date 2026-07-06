"""benchmark.py — the Benchmark descriptor + registry.

Bundles the facts that genuinely differ between benchmarks (task loading,
the workspace port name, grading, oracle-env shape, calibration) into one
small record the CLI can look up by name — the same registry pattern the
codebase already uses six times for arm ports (`WORKSPACE_PORTS`,
`DONE_SIGNAL_PORTS`, `ADVERSARY_ADAPTERS`, ...), applied to the seventh axis.

`grade` is a FACTORY, not the grade callable itself: `Callable[..., Callable]`
that a caller invokes with whatever is genuinely run-specific (BigCodeBench's
`pins`; SWE-bench's `environment_locks`) to produce the actual
`grade(cell, task, workspace)` function `core.orchestrate.make_orchestrator`
takes. The `Benchmark` descriptor only needs to be registered ONCE, at import
time, with no run yet in scope — the factory shape is what makes that
possible without baking a specific run's pins/locks into the registry itself.

`prepare` exists because `done_signal="self_report"` reads `workspace/
solution.py` as "the artifact the agent produced" — true immediately after
the agent terminates for BigCodeBench (the agent writes the file itself,
nothing to prepare), but NOT true for SWE-bench, whose artifact (a diff)
must be extracted from the workspace first. `make_orchestrator` calls
`prepare` (if given) right after the agent terminates and BEFORE done_signal
is consulted, so a benchmark whose self-report artifact is derived, not
directly produced, can make it exist in time. `None` (BigCodeBench's case)
is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Benchmark:
    name: str                      # matches manifest [tasks].benchmark
    load_tasks: Callable           # (manifest, cache_dir) -> list[task dict]
    task_id_key: str                # "task_id" | "instance_id"
    grade: Callable                 # a FACTORY: grade(**run_kwargs) -> grade(cell, task, workspace) -> {"verdict", "extra_row"}
    resolve_oracle_env: Callable | None = None   # (manifest) -> OracleEnv-shaped dict; wired by a later CLI-dispatch pass
    calibrate: Callable | None = None            # (manifest, repo) -> calibration result; wired by a later CLI-dispatch pass
    prepare: Callable | None = None              # (cell, task, workspace) -> None; runs BEFORE done_signal (see below)


_BENCHMARKS: dict[str, Benchmark] = {}


def register(b: Benchmark) -> None:
    _BENCHMARKS[b.name] = b


def resolve(name: str) -> Benchmark:
    """KeyError-with-known-names on an unregistered benchmark — the same
    fail-loud posture `evallib.arms.arm_spec` already takes on an unknown arm
    name, applied to the seventh axis."""
    if name not in _BENCHMARKS:
        known = ", ".join(sorted(_BENCHMARKS)) or "(none registered)"
        raise KeyError(f"unknown benchmark {name!r}; known: {known}")
    return _BENCHMARKS[name]


def known_names() -> list[str]:
    return sorted(_BENCHMARKS)
