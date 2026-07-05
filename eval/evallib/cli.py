"""cli.py — the three eval verbs: plan, run, analyze.

Each verb has a file between it and the next (plan → matrix.jsonl → run →
results.jsonl → analyze → summary.md), so every phase boundary is an
inspectable, diffable artifact. The verbs are thin: all the logic lives in the
evallib modules, each of which is a gated claim.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path


def _load_manifest(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def _resolve_tasks(manifest: dict, cache_dir: Path) -> list[dict]:
    """Resolve the pinned task set for a manifest. Prefers a local JSONL cache
    (hermetic); falls back to a real HuggingFace fetch only when asked."""
    from evallib.taskstore import load_pinned, fetch_bigcodebench_hard
    t = manifest["tasks"]
    local = t.get("local")
    if local:
        return load_pinned(local, t.get("hash"), t.get("count"))
    return fetch_bigcodebench_hard(t["revision"], cache_dir)


def cmd_plan(args) -> int:
    from evallib.plan import expand, write_matrix
    from evallib.adapters.telemetry import estimate_usd
    manifest = _load_manifest(Path(args.manifest))
    run_dir = Path(args.out)
    (run_dir).mkdir(parents=True, exist_ok=True)
    # freeze the manifest at launch so old runs stay legible
    (run_dir / "manifest.toml").write_text(Path(args.manifest).read_text())
    tasks = _resolve_tasks(manifest, run_dir / "cache")
    sample = manifest["tasks"].get("sample")
    if isinstance(sample, dict) and sample.get("n"):
        tasks = tasks[: int(sample["n"])]
    cells = expand(manifest, tasks)
    write_matrix(cells, run_dir / "matrix.jsonl")

    # Resolve + lock the oracle environment — the other half of the experiment,
    # pinned like the dataset. Refuses (drift/unpinnable) rather than guessing.
    from evallib.oracle_docker import build_lock
    from evallib.oracle_env import OracleSpecError, OracleDriftError, parse_oracle_env
    from evallib.oracle_build import missing_image_remediation
    try:
        lock = build_lock(manifest)
    except OracleDriftError as e:
        # A missing/mismatched image: name the one-command remediation so a fresh
        # clone reaches ready-to-plan from committed files alone.
        spec = parse_oracle_env(manifest)
        rem = missing_image_remediation(spec.get("image", ""), spec.get("digest", ""))
        print(f"plan refused: {e}\n{rem}", file=sys.stderr)
        return 1
    except OracleSpecError as e:
        print(f"plan refused: oracle env not resolvable — {e}", file=sys.stderr)
        return 1
    (run_dir / "oracle.lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n")

    est = estimate_usd(cells)
    print(f"planned {len(cells)} cells → {run_dir / 'matrix.jsonl'}")
    print(f"oracle env locked → {run_dir / 'oracle.lock.json'} ({lock['oracle_env_hash']})")
    print(f"cost ceiling (every cell at full budget): ${est:,.2f}")
    return 0


def _calibration_path(repo: Path, oracle_env_hash: str) -> Path:
    """Calibration artifacts are keyed by oracle-env hash, so a changed oracle
    env dereferences to a different (or missing) calibration automatically."""
    return repo / "eval" / "calibrations" / (oracle_env_hash.replace(":", "-") + ".json")


def load_exclusions(manifest: dict, repo: Path) -> dict:
    """The pre-registered {task_id: reason} exclusion table the manifest names
    (`_`-prefixed keys are documentation, not tasks). The empty map if none."""
    ref = manifest.get("tasks", {}).get("exclusions")
    if not ref:
        return {}
    p = repo / "eval" / ref
    if not p.exists():
        return {}
    return {k: v for k, v in json.loads(p.read_text()).items() if not k.startswith("_")}


def assert_spend_admitted(run_dir: Path, repo: Path) -> dict:
    """The spend gate with teeth: return the admitting calibration, or raise
    CalibrationError. No paid cell runs unless a calibration measured THIS oracle
    env (by the lock's hash) against THIS dataset, with the pre-registered
    exclusion table UNTOUCHED and a pass rate over the bar. Called first thing by
    `cmd_run`, before any agent."""
    from evallib.calibration import calibration_admits_spend
    lock = json.loads((run_dir / "oracle.lock.json").read_text())
    manifest = _load_manifest(run_dir / "manifest.toml")
    oeh = lock["oracle_env_hash"]
    dataset_hash = manifest["tasks"].get("hash") or ""
    cal_path = _calibration_path(repo, oeh)
    cal = json.loads(cal_path.read_text()) if cal_path.exists() else None
    return calibration_admits_spend(
        cal, oracle_env_hash=oeh, dataset_hash=dataset_hash,
        exclusions_content=load_exclusions(manifest, repo))


def _git_head(repo: Path) -> str:
    """The recurve engine commit under test — provenance so a row reproduces its
    cell. `unknown` if the run dir is not inside a git tree."""
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def cmd_run(args) -> int:
    import os
    from evallib.runner import run
    from evallib.run_pipeline import make_pipeline_adapter
    from evallib.taskstore import content_hash
    from evallib.calibration import CalibrationError
    from evallib import __version__ as adapter_version
    run_dir = Path(args.rundir)
    repo = Path(__file__).resolve().parents[2]

    # SPEND GATE (with teeth): refuse to run a single paid cell unless the oracle
    # env is calibrated on the canonical solutions. This is FIRST, before tasks or
    # agents — a broken oracle must cost nothing.
    try:
        cal = assert_spend_admitted(run_dir, repo)
    except CalibrationError as e:
        print(f"refusing to spend — {e}", file=sys.stderr)
        return 2

    lock = json.loads((run_dir / "oracle.lock.json").read_text())
    oracle_env_hash = lock["oracle_env_hash"]
    oracle_timeout = int(cal["resolved_timeout"])

    # Grading concurrency must match what the lock recorded (O4) — never grade
    # under a condition the calibration did not account for.
    from evallib.grade_policy import (assert_concurrency_matches, serial_retry_on_timeout,
                                       ConcurrencyMismatch, RWLock)
    try:
        assert_concurrency_matches(args.workers, lock.get("grade_concurrency", 1))
    except ConcurrencyMismatch as e:
        print(f"refusing to spend — {e}", file=sys.stderr)
        return 2

    # Start ONE warm oracle container for the whole run (EV-19) and grade by
    # `docker exec` — the per-grading container tax is paid once, not per cell. A
    # timeout gets one serial retry so contention never becomes a false error (O4).
    warm = None
    if lock.get("mode") == "docker":
        from evallib.warm_oracle import WarmOracle
        from evallib import quarantine
        os.environ.setdefault("RECURVE_ORACLE_TMP", "/private/tmp/recurve-oracle-work")
        os.makedirs(os.environ["RECURVE_ORACLE_TMP"], exist_ok=True)
        warm = WarmOracle(lock["digest"], os.environ["RECURVE_ORACLE_TMP"],
                          platform=lock.get("platform", "linux/amd64"))
        warm.start()
        quarantine.set_grader(serial_retry_on_timeout(warm.grade, RWLock()))

    cells = [json.loads(l) for l in (run_dir / "matrix.jsonl").read_text().splitlines() if l.strip()]
    # Re-resolve the pinned tasks (WITH their hidden `test`) from the frozen
    # manifest — the matrix on disk carries only the statement, never the oracle.
    manifest = _load_manifest(run_dir / "manifest.toml")
    tasks = _resolve_tasks(manifest, run_dir / "cache")
    tasks_by_id = {t["task_id"]: t for t in tasks}
    pins = {t["task_id"]: content_hash([t]) for t in tasks}   # per-task oracle pin

    provenance = {
        "dataset_revision": manifest["tasks"].get("revision") or manifest["tasks"].get("hash"),
        "recurve_commit": _git_head(repo),
        "adapter_version": adapter_version,
        "oracle_env_hash": oracle_env_hash,   # WHICH oracle graded — dereferences to the lock
    }
    oracle_runs = int(manifest.get("oracle", {}).get("runs", 3))
    budgets = manifest["matrix"]["budgets"]
    fallback_budget = int(budgets[0]) if budgets else 0   # per-cell cap wins; this is only the fallback

    adapter = make_pipeline_adapter(
        tasks_by_id, pins, provenance,
        budget=fallback_budget, recurve_cmd="recurve", oracle_runs=oracle_runs,
        oracle_timeout=oracle_timeout)

    try:
        n = run(cells, run_dir / "results.jsonl", adapter,
                workspace_root=run_dir / "cells", workers=args.workers)
    finally:
        if warm is not None:
            from evallib import quarantine
            quarantine.set_grader(None)
            warm.stop()
    print(f"ran {n} cell(s); results → {run_dir / 'results.jsonl'}")
    return 0


def cmd_oracle_build(args) -> int:
    """Derive the oracle image from the committed Dockerfile and reconcile its
    digest against the manifest pin — never silently adopt a rebuilt image."""
    from evallib.oracle_build import build_image, reconcile_digest, OracleImageMismatch
    from evallib.oracle_env import parse_oracle_env
    manifest = _load_manifest(Path(args.manifest))
    spec = parse_oracle_env(manifest)
    repo = Path(__file__).resolve().parents[2]
    dockerfile = repo / "eval" / "oracle" / "Dockerfile.nltk"
    built = build_image(dockerfile, "recurve-bcb-oracle:built", repo / "eval" / "oracle")
    print(f"built oracle image → {built}")
    try:
        reconcile_digest(built, spec["digest"])
    except OracleImageMismatch as e:
        print(f"\n{e}", file=sys.stderr)
        return 1
    print(f"reconciled: matches the manifest pin {spec['digest']}")
    return 0


def cmd_calibrate(args) -> int:
    """Grade all canonical solutions through the FINISHED oracle path (warm
    container) and write the calibration keyed by oracle_env_hash. Sequential by
    design — the timeout derives from clean timings. Refuses if a canonical fails
    without a registered exclusion reason (EV-16/21)."""
    import os
    import time
    from evallib.oracle_docker import build_lock
    from evallib.warm_oracle import WarmOracle
    from evallib import quarantine
    from evallib.calibration import derive_calibration, CalibrationError
    repo = Path(__file__).resolve().parents[2]
    manifest = _load_manifest(Path(args.manifest))
    lock = build_lock(manifest)
    oeh = lock["oracle_env_hash"]
    dataset_hash = manifest["tasks"]["hash"]
    revision = manifest["tasks"]["revision"]
    registered = load_exclusions(manifest, repo)
    cal_file = repo / "eval" / "datasets" / f"bcb-hard-calibration@{revision}.jsonl"
    if not cal_file.exists():
        print(f"calibration set absent: {cal_file}", file=sys.stderr)
        return 1
    tasks = [json.loads(l) for l in cal_file.read_text().splitlines() if l.strip()]
    tmp = os.environ.setdefault("RECURVE_ORACLE_TMP", "/private/tmp/recurve-oracle-work")
    os.makedirs(tmp, exist_ok=True)
    print(f"calibrating {len(tasks)} canonicals on {oeh} ...")

    results, warm = {}, None
    try:
        if lock["mode"] == "docker":
            warm = WarmOracle(lock["digest"], tmp, platform=lock.get("platform", "linux/amd64"))
            warm.start()
            quarantine.set_grader(warm.grade)
        for i, t in enumerate(tasks, 1):
            t0 = time.time()
            try:
                v = quarantine.oracle_verdict(t["test"], t["canonical_program"],
                                             runs=1, timeout=300)["verdict"]
            except Exception:
                v = "error"
            results[t["task_id"]] = {"verdict": v, "seconds": round(time.time() - t0, 3)}
    finally:
        quarantine.set_grader(None)
        if warm:
            warm.stop()

    npass = sum(1 for r in results.values() if r["verdict"] == "pass")
    print(f"canonical pass rate: {npass}/{len(tasks)}")
    try:
        cal = derive_calibration(oeh, dataset_hash, results, registered)
    except CalibrationError as e:
        non_pass = {t: r["verdict"] for t, r in results.items() if r["verdict"] != "pass"}
        print(f"calibration REFUSED: {e}\nnon-pass: {json.dumps(non_pass)}", file=sys.stderr)
        return 1
    out = _calibration_path(repo, oeh)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cal, indent=2, sort_keys=True) + "\n")
    print(f"calibration → {out}")
    print(f"  pass {cal['raw_pass_rate']:.3f}, {len(cal['exclusions'])} exclusions, "
          f"timeout {cal['resolved_timeout']}s")
    return 0


def cmd_analyze(args) -> int:
    from evallib.analyze import analyze_and_emit  # tables + figures, one pass
    run_dir = Path(args.rundir)
    out_dir = run_dir / "analysis"
    analyze_and_emit(run_dir / "results.jsonl", out_dir)
    print(f"analysis → {out_dir}/ (summary.md + figures)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan", help="expand a manifest into a pinned matrix.jsonl")
    sp.add_argument("manifest"); sp.add_argument("--out", required=True, help="run dir")
    sp.set_defaults(fn=cmd_plan)
    sr = sub.add_parser("run", help="drive the matrix as a resumable work queue")
    sr.add_argument("rundir"); sr.add_argument("--workers", type=int, default=1)
    sr.set_defaults(fn=cmd_run)
    sa = sub.add_parser("analyze", help="results.jsonl → deterministic tables")
    sa.add_argument("rundir"); sa.set_defaults(fn=cmd_analyze)
    sc = sub.add_parser("calibrate", help="grade the canonical solutions → keyed calibration")
    sc.add_argument("manifest"); sc.set_defaults(fn=cmd_calibrate)
    so = sub.add_parser("oracle", help="oracle-image operations")
    so_sub = so.add_subparsers(dest="oracle_cmd", required=True)
    sob = so_sub.add_parser("build", help="derive the oracle image + reconcile its digest")
    sob.add_argument("manifest"); sob.set_defaults(fn=cmd_oracle_build)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
