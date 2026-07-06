"""bigcodebench.py — the BigCodeBench Benchmark: grading wrapped as a port.

Reuses `evallib.quarantine.evaluate` / `evallib.taskstore` completely
unchanged — this module is a thin adapter, never a reimplementation.
`grade_bcb` is byte-for-byte the same `evaluate()` call
`evallib.orchestrate.make_orchestrator` makes today, just reachable through
the grade port instead of hardwired inline.
"""

from __future__ import annotations

from pathlib import Path

from evallib.quarantine import OracleTamperError, evaluate
from evallib.taskstore import fetch_bigcodebench_hard, load_pinned

from src.core.benchmark import Benchmark, register


def grade_bcb(pins: dict, *, oracle_runs: int = 3, oracle_timeout: int = 30):
    """The grade factory: `grade_bcb(pins, oracle_runs=..., oracle_timeout=...)`
    returns `grade(cell, task, workspace) -> {"verdict", "extra_row"}`. The
    hidden-test string, the pinned content-hash check, and the
    `OracleTamperError` handling are exactly `evallib.quarantine.evaluate`'s
    own, untouched — this only relocates WHERE that call happens (behind a
    port, not hardwired inside the orchestrator)."""
    def grade(cell: dict, task: dict, workspace) -> dict:
        sol = Path(workspace) / "solution.py"
        solution_src = sol.read_text() if sol.exists() else ""
        try:
            oracle = evaluate(task, solution_src, pins[cell["task_id"]],
                              runs=oracle_runs, timeout=oracle_timeout)
            verdict, flake = oracle["verdict"], oracle["flake_rate"]
        except OracleTamperError:
            verdict, flake = "tampered", 0.0
        return {"verdict": verdict, "extra_row": {"oracle_flake_rate": flake}}
    return grade


def _load_tasks(manifest: dict, cache_dir) -> list[dict]:
    t = manifest["tasks"]
    if t.get("local"):
        # Manifests store `local` relative to `eval/` -- resolve against
        # `cache_dir`'s own parent rather than depending on the caller's cwd.
        local = Path(cache_dir).parent / t["local"]
        return load_pinned(local, t.get("hash"), t.get("count"))
    return fetch_bigcodebench_hard(t["revision"], cache_dir)


def resolve_oracle_env(manifest: dict, *, repo=None, digest_probe=None, python_probe=None) -> dict:
    """A single shared oracle lock for the whole run — the shape a manifest
    with one `[oracle.env]` table has always had. Reuses
    `evallib.oracle_env.parse_oracle_env`/`resolve_oracle_lock` completely
    unchanged; this is a one-line dispatch wrapper, not a reimplementation.
    `repo` is accepted (and unused here) purely so a caller dispatching on
    the `Benchmark` registry can call every benchmark's `resolve_oracle_env`
    the SAME way, without knowing which one it's actually calling; SWE-bench's
    own version genuinely needs it (to locate the per-instance locks file).

    The default `digest_probe` matches `evallib.oracle_docker.build_lock`'s
    OWN wiring exactly: `local_image_digest(image, spec["digest"])`, checked
    by content digest (`docker image inspect <digest>`, or `<image>@<digest>`
    for a pulled image) -- NOT by the bare image name (which implicitly means
    `:latest` and is blind to a real, differently-tagged local image, e.g.
    `recurve-bcb-oracle:built`). A from-scratch reimplementation of this
    probe got exactly that wrong once already; reusing `local_image_digest`
    unchanged is what evallib itself does, and is not optional."""
    from evallib.oracle_docker import local_image_digest
    from evallib.oracle_env import parse_oracle_env, resolve_oracle_lock
    spec = parse_oracle_env(manifest)
    probe = digest_probe or (lambda image: local_image_digest(image, spec["digest"]))
    return resolve_oracle_lock(spec, digest_probe=probe, python_probe=python_probe)


def calibrate(manifest: dict, repo) -> dict | None:
    """The calibration artifact for the CURRENT lock, if one exists on disk
    — reuses `evallib.calibration` completely unchanged; this only resolves
    WHERE the artifact lives for this benchmark's (single-lock) shape."""
    from pathlib import Path
    import json
    oeh = manifest.get("_resolved_oracle_env_hash")
    if not oeh:
        return None
    path = Path(repo) / "eval" / "calibrations" / f"{oeh.replace(':', '-')}.json"
    return json.loads(path.read_text()) if path.exists() else None


register(Benchmark(
    name="bigcodebench-hard",
    load_tasks=_load_tasks,
    task_id_key="task_id",
    grade=grade_bcb,
    resolve_oracle_env=resolve_oracle_env,
    calibrate=calibrate,
))
