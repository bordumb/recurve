from __future__ import annotations

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .. import SCHEMA_VERSION
from ..config import Config, ConfigError, find_config, load
from ..conformance import run_matrix
from ..coverage import coverage
from ..cycle import write_cycle_plan
from ..freshness import gap_freshness
from ..importer import parse_gaps_md, to_yaml_skeleton
from ..model import GapParseError, Ledger, Status, load_ledger
from ..triage import review_gated, triage


def _fail(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _config(args) -> Config:
    path = Path(args.config) if getattr(args, "config", None) else find_config(Path.cwd())
    if path is None:
        _fail("no recurve.toml found from the current directory upward — pass --config")
    try:
        cfg = load(Path(path))
    except ConfigError as e:
        _fail(f"\033[31m✗ config error:\033[0m {e}")
    if cfg.schema_pin and cfg.schema_pin != SCHEMA_VERSION.split(".")[0]:
        _fail(f"\033[31m✗ schema pin mismatch:\033[0m project pins schema {cfg.schema_pin!r}, "
              f"engine ships {SCHEMA_VERSION} — migrate the ledger or the engine, never reinterpret")
    return cfg


def _load(cfg: Config) -> Ledger:
    try:
        return load_ledger(cfg)
    except GapParseError as e:
        print(f"\033[31m✗ ledger parse error:\033[0m {e}", file=sys.stderr)
        raise SystemExit(2)


def _filter(ledger: Ledger, suite: str | None, gap: str | None):
    gaps = list(ledger.gaps)
    if suite:
        gaps = [g for g in gaps if g.suite == suite]
    if gap:
        sel = ledger.by_id(gap)
        if not sel:
            print(f"unknown gap id: {gap}", file=sys.stderr)
            raise SystemExit(2)
        gaps = [sel]
    return gaps


def _parse_point(spec: str):
    """Parse one `ID[:WEIGHT]` surface point from the command line."""
    from ..frontier import SurfacePoint
    id_part, _, w_part = spec.partition(":")
    id_part = id_part.strip()
    if not id_part:
        _fail(f"empty surface point id in {spec!r} — use ID or ID:WEIGHT")
    try:
        weight = int(w_part) if w_part else 0
    except ValueError:
        _fail(f"non-integer weight in {spec!r} — use ID or ID:WEIGHT")
    return SurfacePoint(id_part, weight)


def _parse_goal(spec: str):
    """Parse one `ID[:WEIGHT]` accepted goal-counterexample from the command line.

    A goal named on `--goal` is one that was observed *accepted* this cycle — a
    divergence signal — so it is always constructed with ``accepted=True``."""
    from ..fidelity import GoalCounterexample
    id_part, _, w_part = spec.partition(":")
    id_part = id_part.strip()
    if not id_part:
        _fail(f"empty goal-counterexample id in {spec!r} — use ID or ID:WEIGHT")
    try:
        weight = int(w_part) if w_part else 0
    except ValueError:
        _fail(f"non-integer weight in {spec!r} — use ID or ID:WEIGHT")
    return GoalCounterexample(id_part, accepted=True, weight=weight)


def _draft_backlog(cfg) -> tuple[list[dict], int]:
    """What the strict ledger cannot see: per-suite pending draft counts and
    unresolved adjudication forks. Orchestrators consult this to decide
    whether an empty backlog means 'done' or 'the next wave is unarmed'."""
    import yaml
    drafts = []
    for s in cfg.suites.values():
        p = s.dir / "gaps.draft.yaml"
        if not p.exists():
            continue
        try:
            doc = yaml.safe_load(p.read_text()) or []
        except yaml.YAMLError:
            doc = []
        if isinstance(doc, list) and doc:
            drafts.append({"suite": s.name, "pending": len(doc)})
    adj = cfg.assets_dir / "ADJUDICATE.md"
    forks = adj.read_text().count("DECIDED: (pending") if adj.exists() else 0
    return drafts, forks
