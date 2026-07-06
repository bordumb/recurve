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
from src.core.benchmark import resolve  # noqa: E402


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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="resolve tasks + oracle env for a manifest")
    sp.add_argument("manifest")
    sp.set_defaults(func=cmd_plan)

    sc = sub.add_parser("calibration-status", help="whether a manifest's oracle env(s) are calibrated")
    sc.add_argument("manifest")
    sc.set_defaults(func=cmd_calibration_status)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
