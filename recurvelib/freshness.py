"""Artifact freshness — the regression guard's foundation.

Every probe reads a suite's *copied* build artifact, not the target tree's
build output. So a probe's verdict is only trustworthy if that copy reflects
the CURRENT tree. The danger this closes: a cycle edits the tree and rebuilds
only the suite it's working on, leaving OTHER suites' copies stale — their
probes then run against old artifacts and mask a regression, so the gate
reports a false green.

Freshness is checked PER ARTIFACT CLASS (the `reads:` field on a gap), and
each class's check is a declarative rule from recurve.toml:

  content-hash → the suite artifact is byte-IDENTICAL to the tree's built
                 artifact when fresh (the rebuild step copies it). Precise:
                 it answers "is the suite running the current built tree?"
                 with no mtime guesswork. A source edit not yet built reads
                 as FRESH — correct: the probe then honestly measures the
                 last-built tree.
  mtime        → the suite artifact dir vs the newest source mtime under the
                 rule's source dirs (scoped by suffix, so an unrelated change
                 never flags this class stale).
  none         → not artifact-derived; freshness N/A (the probe guards itself).

UNKNOWN (can't verify: tree not built, or no artifact) never blocks the gate —
the probe's own BROKEN handles a missing artifact, and a missing tree is a
bigger problem the gate can't paper over.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import Config, FreshnessRule, SuiteConfig


class Freshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FreshnessReport:
    suite: str
    scope: str          # the artifact class checked (the `reads:` key)
    state: Freshness
    detail: str

    @property
    def label(self) -> str:
        return f"{self.suite}/{self.scope}"

    @property
    def blocks_gate(self) -> bool:
        return self.state is Freshness.STALE


def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _newest_mtime_in(tree: Path, sources: tuple[str, ...], suffixes: tuple[str, ...],
                     skip_dirs: tuple[str, ...]) -> tuple[float, Path | None]:
    newest, newest_path = 0.0, None
    skip = set(skip_dirs)
    for rel in sources:
        src_root = tree / rel
        if not src_root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                if fn.endswith(tuple(suffixes)):
                    p = Path(dirpath) / fn
                    try:
                        m = p.stat().st_mtime
                    except OSError:
                        continue
                    if m > newest:
                        newest, newest_path = m, p
    return newest, newest_path


def check_freshness(
    config: Config,
    suite: SuiteConfig,
    scope: str,
    rule: FreshnessRule,
    cache: dict,
) -> FreshnessReport:
    name, tree_disp = suite.name, config.tree_display

    if rule.method == "none":
        return FreshnessReport(name, scope, Freshness.FRESH,
                               "not artifact-derived (probe self-guards)")
    if config.tree is None:
        return FreshnessReport(name, scope, Freshness.UNKNOWN,
                               f"platform source ({tree_disp}) not found")

    if rule.method == "content-hash":
        art = suite.dir / rule.artifact
        src = config.tree / rule.source
        if not art.exists():
            return FreshnessReport(name, scope, Freshness.UNKNOWN,
                                   f"no {rule.artifact} — probe stands alone")
        if not src.exists():
            return FreshnessReport(name, scope, Freshness.UNKNOWN,
                                   f"{tree_disp} not built (no {rule.source}) — cannot verify")
        sha_key = ("sha", str(src))
        if sha_key not in cache:
            cache[sha_key] = _file_sha(src)
        if _file_sha(art) == cache[sha_key]:
            return FreshnessReport(name, scope, Freshness.FRESH,
                                   f"{rule.artifact} == {tree_disp}/{rule.source}")
        return FreshnessReport(name, scope, Freshness.STALE,
                               f"{rule.artifact} != {tree_disp}/{rule.source} "
                               f"— rebuild: {suite.rebuild}")

    # mtime
    art_dir = suite.dir / rule.artifact
    arts = [p for p in art_dir.rglob("*") if p.is_file()] if art_dir.is_dir() else []
    if not arts:
        return FreshnessReport(name, scope, Freshness.UNKNOWN,
                               f"no {rule.artifact}/ artifacts — probe stands alone")
    oldest = min(arts, key=lambda p: p.stat().st_mtime)
    key = ("mtime", rule.sources, rule.suffixes)
    if key not in cache:
        cache[key] = _newest_mtime_in(config.tree, rule.sources, rule.suffixes, rule.skip_dirs)
    newest_m, newest_p = cache[key]
    if newest_m > oldest.stat().st_mtime:
        src = newest_p.relative_to(config.tree) if newest_p else "tree source"
        return FreshnessReport(name, scope, Freshness.STALE,
                               f"{tree_disp}/{src} is newer than {oldest.relative_to(suite.dir)} "
                               f"— rebuild: {suite.rebuild}")
    return FreshnessReport(name, scope, Freshness.FRESH,
                           f"{rule.artifact}/ current with {rule.sources_label}")


def gap_freshness(config: Config, suite_name: str, scope: str, cache: dict) -> FreshnessReport:
    """Freshness for one (suite, reads-class) pair. The rule is guaranteed to
    exist: Gap.parse rejected any `reads` value without a configured rule."""
    suite = config.suite_for(suite_name)
    return check_freshness(config, suite, scope, suite.reads[scope], cache)
