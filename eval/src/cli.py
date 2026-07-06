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
from datetime import datetime, timezone
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parent
EXPERIMENTS_ROOT = EVAL / "experiments"
sys.path.insert(0, str(EVAL))

import src.benchmarks.bigcodebench  # noqa: F401,E402 -- registers on import
import src.benchmarks.swebench  # noqa: F401,E402
from src.core.benchmark import known_names, resolve  # noqa: E402
from src.core.orchestrate import make_orchestrator  # noqa: E402
from src.core.runner import run as runner_run  # noqa: E402
from src.core.schema import ManifestError, validate_manifest  # noqa: E402
from src.core import run_index, run_manager, run_meta, run_paths  # noqa: E402


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


def _resolve_run_dir(args, name: str, git_commit: str, oracle_env_hash: str | None):
    """Pick the run directory for this invocation and report its mode.

    Fresh managed (the default) gets a new timestamped directory that never
    collides. `--continue <run-id|latest>` extends an existing run under the
    same experiment, warning if the code or oracle has drifted since it
    started. `--out` is the unmanaged escape hatch — a plain directory with no
    audit trail. Returns (run_dir, managed, is_continue, run_id_or_None)."""
    if args.out and args.continue_run:
        raise ValueError("--out and --continue are mutually exclusive")
    if args.out:
        run_dir = Path(args.out)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir, False, False, None
    if args.continue_run:
        run_dir = run_manager.resolve_continue_target(EXPERIMENTS_ROOT, name, args.continue_run)
        meta = run_meta.read(run_dir / "run_meta.json")
        for w in run_manager.continuation_warnings(meta, git_commit, oracle_env_hash):
            print(f"warning: {w}", file=sys.stderr)
        return run_dir, True, True, None
    run_dir, rid = run_manager.begin_fresh_run(
        EXPERIMENTS_ROOT, name, datetime.now(timezone.utc), git_commit)
    return run_dir, True, False, rid


def cmd_run(args) -> int:
    """Drive a manifest's matrix through the cell pipeline, in one of three run
    modes (fresh managed / --continue / unmanaged --out). Resolving tasks +
    oracle env, the calibration spend gate, materialize + the arm-appropriate
    agent, and the grade port are all dispatched through the Benchmark
    registry, one code path for every benchmark. `--dry-run` swaps every
    expensive step for a fake agent/grade/gate: zero cost, zero docker."""
    manifest = _load_manifest(args.manifest)
    try:
        validate_manifest(manifest, known_benchmarks=known_names())
    except ManifestError as e:
        print(f"manifest invalid -- {e}", file=sys.stderr)
        return 2
    bench = _benchmark(manifest)
    name = manifest["experiment"]["name"]

    from evallib import __version__ as adapter_version
    from evallib.cli import _git_head
    git_commit = _git_head(REPO)

    tasks = bench.load_tasks(manifest, EVAL / "datasets")
    sample = manifest["tasks"].get("sample")
    sample_n = int(sample["n"]) if isinstance(sample, dict) and sample.get("n") else None
    if sample_n:
        tasks = tasks[:sample_n]
    tasks_by_id = {t[bench.task_id_key]: t for t in tasks}

    # A dry run grades with a fake port and never touches the oracle, so it must
    # not probe docker to resolve an oracle env (that would break its zero-docker
    # promise). A real run resolves the env for the spend gate and grading.
    env = None
    if not args.dry_run and bench.resolve_oracle_env:
        env = bench.resolve_oracle_env(manifest, repo=REPO)
    is_single_lock = isinstance(env, dict) and "oracle_env_hash" in env
    oracle_env_hash = env["oracle_env_hash"] if is_single_lock else None

    try:
        run_dir, managed, is_continue, rid = _resolve_run_dir(
            args, name, git_commit, oracle_env_hash)
    except FileExistsError:
        print("cannot start run -- a run for this second and commit already "
              "exists; wait a moment for a fresh run, or use --continue to "
              "extend it", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError) as e:
        print(f"cannot start run -- {e}", file=sys.stderr)
        return 2

    # Freeze the manifest for a fresh or unmanaged run; a continuation keeps the
    # frozen copy its first batch already wrote.
    if not is_continue:
        (run_dir / "manifest.toml").write_text(Path(args.manifest).read_text())

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

    provenance = {
        "dataset_revision": manifest["tasks"].get("revision") or manifest["tasks"].get("hash"),
        "recurve_commit": git_commit,
        "adapter_version": adapter_version,
    }
    if is_single_lock:
        provenance["oracle_env_hash"] = oracle_env_hash

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
    # BigCodeBench's agent, which does the same for real) -- a real benchmark's
    # `prepare` derives that artifact (SWE-bench's diff extraction), which is
    # exactly the mechanism dry-run is not testing.
    prepare = None if args.dry_run else bench.prepare
    orchestrate = make_orchestrator(agent, tasks_by_id, provenance,
                                    grade=grade, gate_fn=gate_fn, prepare=prepare)

    n = runner_run(cells, run_dir / "results.jsonl", orchestrate, run_dir / "cells",
                   workers=args.workers, keep_workspaces=args.keep_workspaces)

    # Record the audit trail for a managed run (the unmanaged --out escape hatch
    # deliberately leaves none).
    if managed:
        common = dict(now=datetime.now(timezone.utc), git_commit=git_commit,
                      oracle_env_hash=oracle_env_hash, sample_n=sample_n, cells_added=n)
        if is_continue:
            run_manager.record_continuation(run_dir, EXPERIMENTS_ROOT, name, **common)
        else:
            run_manager.record_fresh(
                run_dir, EXPERIMENTS_ROOT, name, rid, adapter_version=adapter_version,
                manifest_hash=run_manager.manifest_hash(Path(args.manifest).read_text()),
                command=list(sys.argv), **common)

    label = "[dry-run] " if args.dry_run else ""
    mode = "unmanaged" if not managed else ("continued" if is_continue else "fresh")
    print(f"{label}ran {n} cell(s); results -> {run_dir / 'results.jsonl'}")
    print(f"  run: {run_dir}  ({mode})")
    return 0


def cmd_run_history(args) -> int:
    """Print an experiment's whole run history from its index -- run id, event,
    commit, and cells added per batch -- without opening any run directory."""
    rows = run_index.read_all(run_paths.index_path(EXPERIMENTS_ROOT, args.experiment))
    if not rows:
        print(f"no runs recorded for experiment {args.experiment!r}")
        return 0
    print(f"{'run_id':<26} {'event':<10} {'commit':<9} {'cells':>5}  at")
    for r in rows:
        print(f"{r.get('run_id', ''):<26} {r.get('event', ''):<10} "
              f"{str(r.get('git_commit', ''))[:7]:<9} {r.get('cells_added', 0):>5}  {r.get('at', '')}")
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
    sr.add_argument("--out", help="unmanaged run directory (no audit trail); omit for a fresh managed run")
    sr.add_argument("--continue", dest="continue_run", metavar="RUN_ID|latest",
                    help="extend an existing managed run under the same experiment")
    sr.add_argument("--workers", type=int, default=1)
    sr.add_argument("--keep-workspaces", action="store_true",
                    help="skip post-seal workspace GC; useful for debugging one cell")
    sr.add_argument("--dry-run", action="store_true",
                    help="fake agent/grade/gate wiring -- zero cost, zero docker")
    sr.set_defaults(func=cmd_run)

    sh = sub.add_parser("run-history", help="print an experiment's run history from its index")
    sh.add_argument("experiment", help="experiment name (matches [experiment].name)")
    sh.set_defaults(func=cmd_run_history)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
