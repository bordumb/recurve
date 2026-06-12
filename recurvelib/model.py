"""Typed domain model for the improvement loop.

Parse, don't validate: `Gap.parse` and `load_ledger` are TOTAL boundary
functions — they either return a fully-formed, internally-consistent object or
raise `GapParseError` with a precise, file-located message. Nothing downstream
re-checks a field; if you hold a `Gap`, its invariants already hold. This is
the same discipline the quality constitution asks of the changes the loop
produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .config import Config


class GapParseError(ValueError):
    """A gaps.yaml entry could not be parsed into a valid Gap."""


class GapClass(str, Enum):
    """The closed six. New domains get a Conventions section in their GAPS.md
    prose, never new enum values — `security-tradeoff`'s review-gating
    semantics are load-bearing and must not be diluted by proliferation."""

    MISSING_SURFACE = "missing-surface"      # a surface the product should have
    BROKEN_ROUTE = "broken-route"            # two product parts that don't compose
    WIRE_MISMATCH = "wire-mismatch"          # implementations disagree on bytes
    SECURITY_TRADEOFF = "security-tradeoff"  # deliberate fail-closed that over-rejects
    STAGING = "staging"                      # single-box / simulator compromise
    FRICTION = "friction"                    # rough edge, not load-bearing


class Status(str, Enum):
    OPEN = "open"            # not yet sculpted; probe expected RED
    SCULPTING = "sculpting"  # a cycle owns it; probe expected RED until it lands
    CLOSED = "closed"        # fixed; probe expected GREEN, guards regression forever
    PERMANENT = "permanent"  # a fact of the world; never triaged, no probe


class Severity(str, Enum):
    HEADLINE = "headline"   # changes what the target can claim
    FEATURE = "feature"     # a real capability the target lacks
    FRICTION = "friction"   # scripting/ergonomic rough edge
    COSMETIC = "cosmetic"   # wording / polish


# Statuses whose probe SHOULD be red today (the gap is still open).
_RED_EXPECTED = {Status.OPEN, Status.SCULPTING}


@dataclass(frozen=True)
class Gap:
    id: str
    suite: str
    title: str
    gap_class: GapClass
    status: Status
    severity: Severity
    evidence: tuple[str, ...]
    observed: str
    smallest_fix: str
    unlocks: str
    reads: str               # which artifact class the probe reads (freshness axis)
    covers: tuple[str, ...]  # GAPS.md section anchors (prose↔ledger link)
    # Absolute path to the probe executable, or None for `permanent`/un-authored.
    probe: Path | None
    source_file: Path        # the gaps.yaml this came from (for error messages)
    trap_waiver: str = ""    # reason this probe carries no trap (counted, visible debt)

    @property
    def trap_dir(self) -> Path | None:
        """probes/<name>.sh pairs with probes/<name>.trap/ — one subdirectory
        per counterexample fixture the probe must turn RED."""
        if self.probe is None:
            return None
        return self.probe.parent / (self.probe.stem + ".trap")

    @property
    def traps(self) -> tuple[Path, ...]:
        d = self.trap_dir
        if d is None or not d.is_dir():
            return ()
        return tuple(sorted(p for p in d.iterdir() if p.is_dir()))

    @property
    def suite_dir(self) -> Path:
        """The suite directory — gaps.yaml lives at its root."""
        return self.source_file.parent

    @property
    def needs_probe(self) -> bool:
        """An open/sculpting/closed gap without a probe is an opinion, not a gap."""
        return self.status is not Status.PERMANENT

    @property
    def expects_red(self) -> bool:
        return self.status in _RED_EXPECTED

    @staticmethod
    def parse(
        raw: Any,
        suite: str,
        suite_dir: Path,
        source_file: Path,
        allowed_reads: tuple[str, ...],
        default_reads: str,
    ) -> "Gap":
        if not isinstance(raw, dict):
            raise GapParseError(f"{source_file}: gap entry is not a mapping: {raw!r}")

        def req(key: str) -> Any:
            if key not in raw or raw[key] in (None, ""):
                raise GapParseError(f"{source_file}: gap {raw.get('id', '?')!r} missing required '{key}'")
            return raw[key]

        def enum(key: str, kind: type[Enum]) -> Any:
            val = req(key)
            try:
                return kind(val)
            except ValueError:
                allowed = ", ".join(m.value for m in kind)  # type: ignore[attr-defined]
                raise GapParseError(
                    f"{source_file}: gap {raw.get('id')!r} has {key}={val!r}; allowed: {allowed}"
                )

        gid = str(req("id"))
        status = enum("status", Status)

        # `reads` is an open string, but it must name a configured freshness
        # rule — a probe whose artifact class the runner can't check for
        # staleness could return verdicts that are lies.
        reads = str(raw.get("reads", default_reads))
        if reads not in allowed_reads:
            allowed = ", ".join(allowed_reads)
            raise GapParseError(f"{source_file}: gap {gid!r} has reads={reads!r}; allowed: {allowed}")

        evidence_raw = raw.get("evidence") or []
        if not isinstance(evidence_raw, list):
            raise GapParseError(f"{source_file}: gap {gid!r} 'evidence' must be a list")
        evidence = tuple(str(e) for e in evidence_raw)

        covers_raw = raw.get("covers") or []
        if not isinstance(covers_raw, list):
            raise GapParseError(f"{source_file}: gap {gid!r} 'covers' must be a list of GAPS.md anchors")
        covers = tuple(str(c) for c in covers_raw)

        probe_field = raw.get("probe")
        probe: Path | None = None
        if probe_field:
            probe = (suite_dir / str(probe_field)).resolve()

        # The parse-time invariant the whole loop rests on: a non-permanent gap
        # must name a probe. We allow the file to be absent here (intake may be
        # mid-flight) — `validate` reports missing files — but a null probe
        # field on a real gap is a hard parse error: it can never be measured.
        if status is not Status.PERMANENT and probe is None:
            raise GapParseError(
                f"{source_file}: gap {gid!r} is {status.value} but names no 'probe'. "
                f"A gap without a probe is an opinion — author probes/<id>.sh first."
            )

        return Gap(
            id=gid,
            suite=suite,
            title=str(req("title")),
            gap_class=enum("class", GapClass),
            status=status,
            severity=enum("severity", Severity),
            evidence=evidence,
            observed=str(raw.get("observed", "")),
            smallest_fix=str(req("smallest_fix")).strip(),
            unlocks=str(raw.get("unlocks", "")).strip(),
            reads=reads,
            covers=covers,
            probe=probe,
            source_file=source_file,
            trap_waiver=str(raw.get("trap_waiver", "")).strip(),
        )


@dataclass(frozen=True)
class SuiteLedger:
    suite: str
    suite_dir: Path
    gaps: tuple[Gap, ...]


@dataclass(frozen=True)
class Ledger:
    """All gaps across every configured suite, parsed once at the boundary."""

    suites: tuple[SuiteLedger, ...]

    @property
    def gaps(self) -> tuple[Gap, ...]:
        return tuple(g for s in self.suites for g in s.gaps)

    def by_id(self, gap_id: str) -> Gap | None:
        return next((g for g in self.gaps if g.id == gap_id), None)

    def select(self, ids: list[str]) -> list[Gap]:
        found, missing = [], []
        for gid in ids:
            g = self.by_id(gid)
            (found if g else missing).append(g if g else gid)
        if missing:
            raise GapParseError(f"unknown gap id(s): {', '.join(str(m) for m in missing)}")
        return found  # type: ignore[return-value]


def load_ledger(config: Config) -> Ledger:
    """Parse every configured suite's gaps.yaml. Suites are explicit in
    recurve.toml — never discovered by glob, so no sibling directory can
    pollute the ledger. A suite without a gaps.yaml contributes no gaps
    (coverage reports it as ledger-less)."""
    suites: list[SuiteLedger] = []
    for name, sc in config.suites.items():
        gaps_file = sc.dir / "gaps.yaml"
        if not gaps_file.exists():
            continue
        try:
            doc = yaml.safe_load(gaps_file.read_text()) or []
        except yaml.YAMLError as e:
            raise GapParseError(f"{gaps_file}: invalid YAML: {e}") from e
        if not isinstance(doc, list):
            raise GapParseError(f"{gaps_file}: top level must be a list of gaps")
        allowed = tuple(sc.reads.keys())
        gaps = tuple(
            Gap.parse(raw, name, sc.dir, gaps_file, allowed, config.default_reads)
            for raw in doc
        )
        _assert_unique_ids(gaps, gaps_file)
        suites.append(SuiteLedger(suite=name, suite_dir=sc.dir, gaps=gaps))
    return Ledger(suites=tuple(suites))


def _assert_unique_ids(gaps: tuple[Gap, ...], source: Path) -> None:
    seen: set[str] = set()
    for g in gaps:
        if g.id in seen:
            raise GapParseError(f"{source}: duplicate gap id {g.id!r}")
        seen.add(g.id)
