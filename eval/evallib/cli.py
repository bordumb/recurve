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
    est = estimate_usd(cells)
    print(f"planned {len(cells)} cells → {run_dir / 'matrix.jsonl'}")
    print(f"cost ceiling (every cell at full budget): ${est:,.2f}")
    return 0


def _git_head(repo: Path) -> str:
    """The recurve engine commit under test — provenance so a row reproduces its
    cell. `unknown` if the run dir is not inside a git tree."""
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def cmd_run(args) -> int:
    from evallib.runner import run
    from evallib.run_pipeline import make_pipeline_adapter
    from evallib.taskstore import content_hash
    from evallib import __version__ as adapter_version
    run_dir = Path(args.rundir)
    cells = [json.loads(l) for l in (run_dir / "matrix.jsonl").read_text().splitlines() if l.strip()]

    # Re-resolve the pinned tasks (WITH their hidden `test`) from the frozen
    # manifest — the matrix on disk carries only the statement, never the oracle.
    manifest = _load_manifest(run_dir / "manifest.toml")
    tasks = _resolve_tasks(manifest, run_dir / "cache")
    tasks_by_id = {t["task_id"]: t for t in tasks}
    pins = {t["task_id"]: content_hash([t]) for t in tasks}   # per-task oracle pin

    repo = Path(__file__).resolve().parents[2]
    provenance = {
        "dataset_revision": manifest["tasks"].get("revision") or manifest["tasks"].get("hash"),
        "recurve_commit": _git_head(repo),
        "adapter_version": adapter_version,
    }
    oracle_runs = int(manifest.get("oracle", {}).get("runs", 3))
    budgets = manifest["matrix"]["budgets"]
    fallback_budget = int(budgets[0]) if budgets else 0   # per-cell cap wins; this is only the fallback

    adapter = make_pipeline_adapter(
        tasks_by_id, pins, provenance,
        budget=fallback_budget, recurve_cmd="recurve", oracle_runs=oracle_runs)

    n = run(cells, run_dir / "results.jsonl", adapter,
            workspace_root=run_dir / "cells", workers=args.workers)
    print(f"ran {n} cell(s); results → {run_dir / 'results.jsonl'}")
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
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
