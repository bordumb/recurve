"""Coverage — does the machine ledger mirror the GAPS.md prose?

The loop only ever works what's in `gaps.yaml`; anything documented in GAPS.md
prose but absent from the ledger is invisible to it, so the loop can reach
"matrix all green" while real gaps still sit in the prose. Coverage closes
that blind spot: every gap-bearing GAPS.md section must be linked to a ledger
entry via its `covers:` anchor list, or it shows up here as an ORPHAN to
import + probe.

A prose section is "gap-bearing" unless it is narrative (overview / "falls
short" / verdict maps) or already marked CLOSED in its heading. Anchors are
the leading section token: `4`, `6b`, `8`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .importer import parse_gaps_md
from .model import Ledger

_NARRATIVE = ("falls short", "where this", "verdict map", "overview")


@dataclass(frozen=True)
class SuiteCoverage:
    suite: str
    covered: tuple[str, ...]      # prose anchors with a ledger entry
    orphans: tuple[tuple[str, str], ...]  # (anchor, title) prose gaps with NO ledger entry
    closed: tuple[str, ...]       # prose anchors marked CLOSED (done, fine)
    has_ledger: bool

    @property
    def complete(self) -> bool:
        return not self.orphans


def suite_coverage(suite: str, suite_dir: Path, ledger: Ledger) -> SuiteCoverage:
    gaps_md = suite_dir / "GAPS.md"
    sections = parse_gaps_md(gaps_md.read_text()) if gaps_md.exists() else []

    entries = [g for g in ledger.gaps if g.suite == suite]
    has_ledger = (suite_dir / "gaps.yaml").exists()
    covered_anchors = {c for g in entries for c in g.covers}

    covered, orphans, closed = [], [], []
    for s in sections:
        title_l = s.title.lower()
        if any(n in title_l for n in _NARRATIVE):
            continue  # narrative section, not a gap
        if "closed" in title_l:
            closed.append(s.num)
            continue
        if s.num in covered_anchors:
            covered.append(s.num)
        else:
            orphans.append((s.num, s.title))

    return SuiteCoverage(
        suite=suite,
        covered=tuple(covered),
        orphans=tuple(orphans),
        closed=tuple(closed),
        has_ledger=has_ledger,
    )


def coverage(config: Config, ledger: Ledger) -> list[SuiteCoverage]:
    """One report per configured suite that has prose. Suites are the explicit
    config list — coverage never globs for GAPS.md files."""
    reports = []
    for name, sc in config.suites.items():
        if not (sc.dir / "GAPS.md").exists():
            continue
        reports.append(suite_coverage(name, sc.dir, ledger))
    return reports
