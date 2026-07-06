#!/usr/bin/env python3
"""cli.py — one CLI for N benchmarks: dispatch on `manifest["tasks"]["benchmark"]`
through the registry, never a hardcoded benchmark name.

The old CLI (`evallib/cli.py`) hardcodes BigCodeBench in `_resolve_tasks`,
calibration file naming, and oracle-lock writing — SWE-bench has no runnable
verb there at all, despite its own code's error messages naming commands
(`eval swebench build`/`eval swebench plan`) that don't exist. This module
resolves the benchmark ONCE, from the manifest, and calls descriptor methods
— the CLI itself never learns any benchmark's name.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parent
sys.path.insert(0, str(EVAL))

import src.benchmarks.bigcodebench  # noqa: F401,E402 -- registers on import
import src.benchmarks.swebench  # noqa: F401,E402
from src.core.benchmark import known_names, resolve  # noqa: E402
from src.core.orchestrate import make_orchestrator  # noqa: E402
from src.core.runner import run as runner_run  # noqa: E402
from src.core.schema import ManifestError, validate_manifest  # noqa: E402


def _load_manifest(path: Path) -> dict:
    return tomllib.loads(Path(path).read_text())


def _benchmark(manifest: dict):
    name = manifest.get("tasks", {}).get("benchmark")
    if not name:
        raise KeyError('manifest has no [tasks].benchmark -- required to dispatch')
    return resolve(name)


def cmd_plan(args) -> int:
    """Resolve tasks + oracle env for a manifest, through whichever
    benchmark it names -- one code path, not one per benchmark."""
    manifest = _load_manifest(args.manifest)
    bench = _benchmark(manifest)
    tasks = bench.load_tasks(manifest, EVAL / "datasets")
    print(f"benchmark: {bench.name}")
    print(f"tasks loaded: {len(tasks)} (task_id_key={bench.task_id_key!r})")
    for t in tasks[:3]:
        print(f"  - {t[bench.task_id_key]}")
    if len(tasks) > 3:
        print(f"  ... and {len(tasks) - 3} more")

    if bench.resolve_oracle_env is not None:
        try:
            env = bench.resolve_oracle_env(manifest, repo=REPO)
            if isinstance(env, dict) and "oracle_env_hash" in env:
                print(f"oracle env: single lock, oracle_env_hash={env['oracle_env_hash']}")
            else:
                print(f"oracle env: per-instance locks for {len(env)} instance(s)")
        except Exception as e:  # noqa: BLE001 -- report, this is a diagnostic verb
            print(f"oracle env: could not resolve -- {type(e).__name__}: {e}")
    else:
        print("oracle env: no resolve_oracle_env wired for this benchmark yet")
    return 0


def cmd_calibration_status(args) -> int:
    """Whether a calibration artifact exists for this manifest's currently
    resolvable oracle env(s) -- again, one code path for both shapes."""
    manifest = _load_manifest(args.manifest)
    bench = _benchmark(manifest)
    if bench.calibrate is None:
        print(f"{bench.name}: no calibrate() wired yet")
        return 1
    env = bench.resolve_oracle_env(manifest, repo=REPO)
    if isinstance(env, dict) and "oracle_env_hash" in env:
        cal = bench.calibrate({**manifest, "_resolved_oracle_env_hash": env["oracle_env_hash"]}, REPO)
        print(f"{bench.name}: calibration {'PRESENT' if cal else 'MISSING'} "
              f"(oracle_env_hash={env['oracle_env_hash']})")
        return 0 if cal else 1
    ok = True
    for instance_id, lock in env.items():
        cal = bench.calibrate({"_resolved_environment_image_hash": lock["environment_image_hash"]}, REPO)
        status = "PRESENT" if cal else "MISSING"
        print(f"{bench.name}/{instance_id}: calibration {status} "
              f"(environment_image_hash={lock['environment_image_hash']})")
        ok = ok and bool(cal)
    return 0 if ok else 1


def _make_dry_run_ports():
    """The exact fake shape `run_sw6_smoke.py`'s own `SW6_DRY_RUN=1` mode
    uses: a plumbing check, not a mock of the mechanism itself (that stays
    the gated probes'/hermetic tests' job). Zero cost, zero docker, zero
    real `recurve` CLI -- proves plan -> materialize-stub -> agent-stub ->
    orchestrate -> runner wires together for a given manifest before any
    real cell ever runs."""
    def fake_agent(cell: dict, workspace) -> dict:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "solution.py").write_text("# --dry-run stub, no real agent ran\n")
        return {"terminated": True, "agent_exit": 0, "stop_reason": "single_shot",
               "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}

    def fake_grade(cell: dict, task: dict, workspace) -> dict:
        return {"verdict": "pass", "extra_row": {}}

    def fake_gate_fn(workspace) -> str:
        return "green"

    return fake_agent, fake_grade, fake_gate_fn


def cmd_run(args) -> int:
    """The missing driver: plan (resolve tasks + oracle env) -> the
    calibration spend gate -> materialize + the arm-appropriate agent ->
    orchestrate (grade port + prepare + done_signal) -> the resumable,
    GC'd runner -- ONE code path for both benchmarks, dispatched through
    the Benchmark registry the same way `cmd_plan`/`cmd_calibration_status`
    already do. `--dry-run` swaps every expensive/paid step for the exact
    fake shape `run_sw6_smoke.py` proved this same wiring with: zero cost,
    zero docker, zero real agent."""
    manifest = _load_manifest(args.manifest)
    try:
        validate_manifest(manifest, known_benchmarks=known_names())
    except ManifestError as e:
        print(f"manifest invalid -- {e}", file=sys.stderr)
        return 2
    bench = _benchmark(manifest)

    run_dir = Path(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.toml").write_text(Path(args.manifest).read_text())   # freeze at launch

    tasks = bench.load_tasks(manifest, EVAL / "datasets")
    sample = manifest["tasks"].get("sample")
    if isinstance(sample, dict) and sample.get("n"):
        tasks = tasks[: int(sample["n"])]
    tasks_by_id = {t[bench.task_id_key]: t for t in tasks}

    env = bench.resolve_oracle_env(manifest, repo=REPO) if bench.resolve_oracle_env else None
    is_single_lock = isinstance(env, dict) and "oracle_env_hash" in env

    if not args.dry_run and bench.admits_spend is not None:
        try:
            bench.admits_spend(manifest, env, REPO)
        except Exception as e:  # noqa: BLE001 -- refuse, don't crash; the message IS the point
            print(f"refusing to spend -- {e}", file=sys.stderr)
            return 2

    from evallib.plan import write_matrix
    from src.core.plan import expand
    cells = expand(manifest, tasks, bench.task_id_key)
    write_matrix(cells, run_dir / "matrix.jsonl")

    from evallib import __version__ as adapter_version
    from evallib.cli import _git_head
    provenance = {
        "dataset_revision": manifest["tasks"].get("revision") or manifest["tasks"].get("hash"),
        "recurve_commit": _git_head(REPO),
        "adapter_version": adapter_version,
    }
    if is_single_lock:
        provenance["oracle_env_hash"] = env["oracle_env_hash"]

    budgets = manifest["matrix"]["budgets"]
    budget = budgets[0] if budgets else 0

    if args.dry_run:
        agent, grade, gate_fn = _make_dry_run_ports()
    else:
        gate_fn = bench.gate_fn
        if is_single_lock:
            from evallib.taskstore import content_hash
            pins = {t[bench.task_id_key]: content_hash([t]) for t in tasks}
            oracle_runs = int(manifest.get("oracle", {}).get("runs", 3))
            grade = bench.grade(pins, oracle_runs=oracle_runs)
        else:
            grade = bench.grade(env)
        agent = bench.make_routed_agent(tasks_by_id, env, budget=budget, recurve_cmd="recurve")

    # --dry-run's fake_agent already writes solution.py itself (mirroring
    # BigCodeBench's agent, which does the same for real) -- a real
    # benchmark's `prepare` exists to derive that artifact (SWE-bench's
    # diff extraction), which is exactly the mechanism dry-run is not
    # testing (and which test_end_to_end_sw6.py/tests/e2e already prove
    # separately); running it here would need real benchmark-specific
    # workspace scaffolding (e.g. a git repo under testbed/) inside what is
    # meant to be a benchmark-agnostic plumbing check.
    prepare = None if args.dry_run else bench.prepare
    orchestrate = make_orchestrator(agent, tasks_by_id, provenance,
                                    grade=grade, gate_fn=gate_fn, prepare=prepare)

    n = runner_run(cells, run_dir / "results.jsonl", orchestrate, run_dir / "cells",
                   workers=args.workers, keep_workspaces=args.keep_workspaces)
    print(f"{'[dry-run] ' if args.dry_run else ''}ran {n} cell(s); "
         f"results -> {run_dir / 'results.jsonl'}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="resolve tasks + oracle env for a manifest")
    sp.add_argument("manifest")
    sp.set_defaults(func=cmd_plan)

    sc = sub.add_parser("calibration-status", help="whether a manifest's oracle env(s) are calibrated")
    sc.add_argument("manifest")
    sc.set_defaults(func=cmd_calibration_status)

    sr = sub.add_parser("run", help="drive a manifest's matrix through a real (or --dry-run) cell pipeline")
    sr.add_argument("manifest")
    sr.add_argument("--out", required=True, help="run directory (manifest.toml/matrix.jsonl/results.jsonl land here)")
    sr.add_argument("--workers", type=int, default=1)
    sr.add_argument("--keep-workspaces", action="store_true",
                    help="skip post-seal workspace GC (core/runner.py); useful for debugging one cell")
    sr.add_argument("--dry-run", action="store_true",
                    help="the exact fake agent/grade/gate wiring run_sw6_smoke.py's own SW6_DRY_RUN=1 uses -- zero cost, zero docker")
    sr.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
