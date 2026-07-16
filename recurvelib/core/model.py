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

from recurvelib.core.config import Config


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
    oracle_waiver: str = ""  # reason the probe's external oracle may be absent — a
                             # SKIP (exit 3) is then non-blocking, counted, visible debt
    # Absolute path to a stricter/slower reference oracle, or None. `drill
    # --diff` runs it beside the probe and alarms on disagreement.
    reference: Path | None = None
    # AI9: a claim-level floor on the governor tier — resolves to AT LEAST
    # this strength regardless of a weaker suite-wide `[gate] governor=`
    # default (recurvelib.adapters.policy.effective_governor_tier). Empty
    # means "no floor, use the suite default" — no behavior change for the
    # common case.
    min_governor_tier: str = ""
    # The decomposition edge (autonomous_solver.md §1.3): parent claim id(s)
    # this gap is a LEAF of. Distinct from `covers` (GAPS.md prose anchors —
    # documentation linkage) — this is a claim-to-claim DAG edge a solver
    # walks to discharge a parent once every child closes (`Ledger.parents_of`
    # / `.children_of`). Empty means "not part of a decomposition" — no
    # behavior change for any existing gap.
    covers_claim: tuple[str, ...] = ()
    # The logical/proof dependency edge (issue #24): claim id(s) this claim's
    # proof (or implementation) *uses*. Orthogonal to `covers_claim`: that is
    # decomposition (a parent is a fan-out of its leaves), this is the
    # load-bearing spine (A cannot close until B does). Agnostic — recurve
    # stores ids and never asks how the dependency was derived. Empty means
    # "no declared dependency" — no behavior change for any existing gap.
    depends_on: tuple[str, ...] = ()
    # An opaque grouping label (issue #24) — a project's phase/layer/taxonomy
    # tag that recurve stores and echoes but NEVER interprets. Deliberately
    # NOT `tier` (that is the derived oracle tier and is refused, see parse).
    # Empty means "ungrouped".
    group: str = ""

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
    def falsifier_dir(self) -> Path | None:
        """probes/<name>.sh may ALSO pair with probes/<name>.falsifiers/ — the
        structural inverse of .trap/, a battery of kill-attempts for a conjecture
        (docs/plans/explore-mode.md). A trap guards a claim believed true; a
        falsifier battery tests whether an open lead is still alive. Presence of
        this dir marks the claim as an explore-mode conjecture, scored on the
        survival gradient in ADDITION to its probe — no new GapClass, no dilution
        of the closed six."""
        if self.probe is None:
            return None
        return self.probe.parent / (self.probe.stem + ".falsifiers")

    @property
    def is_conjecture(self) -> bool:
        """An open claim carrying a non-empty falsifier battery is a conjecture —
        a lead being explored, not just a defect being closed."""
        d = self.falsifier_dir
        return d is not None and d.is_dir() and any(p.is_dir() for p in d.iterdir())

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

        # The oracle tier (recurvelib.analysis.oracle_tier) is ALWAYS derived
        # from recorded pass evidence — it is never a ledger field. A gap
        # authoring its own 'tier' is exactly the self-reported-tier gaming
        # this refusal exists to prevent.
        if "tier" in raw:
            raise GapParseError(
                f"{source_file}: gap {raw.get('id', '?')!r} sets 'tier' directly — "
                f"oracle tier is derived from recorded evidence, never hand-set "
                f"(see recurvelib.analysis.oracle_tier)"
            )

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

        covers_claim_raw = raw.get("covers_claim") or []
        if not isinstance(covers_claim_raw, list):
            raise GapParseError(
                f"{source_file}: gap {gid!r} 'covers_claim' must be a list of parent claim ids"
            )
        covers_claim = tuple(str(c) for c in covers_claim_raw)
        if gid in covers_claim:
            raise GapParseError(f"{source_file}: gap {gid!r} names itself in 'covers_claim' — a claim cannot be its own parent")

        depends_on_raw = raw.get("depends_on") or []
        if not isinstance(depends_on_raw, list):
            raise GapParseError(
                f"{source_file}: gap {gid!r} 'depends_on' must be a list of claim ids"
            )
        depends_on = tuple(str(d) for d in depends_on_raw)
        if gid in depends_on:
            raise GapParseError(
                f"{source_file}: gap {gid!r} names itself in 'depends_on' — a claim cannot depend on itself"
            )

        # `group` is an opaque passthrough — any string. It is NOT `tier`
        # (refused above); recurve stores it and never interprets it.
        group = str(raw.get("group", "")).strip()

        probe_field = raw.get("probe")
        probe: Path | None = None
        if probe_field:
            probe = (suite_dir / str(probe_field)).resolve()

        reference_field = raw.get("reference")
        reference: Path | None = None
        if reference_field:
            reference = (suite_dir / str(reference_field)).resolve()

        # AI9: a claim-level governor-tier floor, validated against the known
        # vocabulary at parse time — an unrecognized value is a parse error,
        # never a silently-ignored typo.
        min_governor_tier = str(raw.get("min_governor_tier", "")).strip()
        if min_governor_tier and min_governor_tier not in (
            "off", "mechanical", "mechanical_review", "human_required"
        ):
            raise GapParseError(
                f"{source_file}: gap {gid!r} has min_governor_tier={min_governor_tier!r}; "
                f"allowed: off, mechanical, mechanical_review, human_required"
            )

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
            oracle_waiver=str(raw.get("oracle_waiver", "")).strip(),
            reference=reference,
            min_governor_tier=min_governor_tier,
            covers_claim=covers_claim,
            depends_on=depends_on,
            group=group,
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

    def children_of(self, parent_id: str) -> list[Gap]:
        """Every gap whose `covers_claim` names `parent_id` — the leaves (and
        assembly) of a decomposition, in ledger order. Unknown `parent_id`
        (no gap has it as a parent, or it doesn't exist) yields an empty
        list — this is a query, not an assertion the id exists."""
        return [g for g in self.gaps if parent_id in g.covers_claim]

    def parents_of(self, child_id: str) -> list[Gap]:
        """The claim(s) `child_id` is a decomposition leaf of. A gap with no
        `covers_claim` (not part of any decomposition) yields an empty list.
        Raises `GapParseError` only if `child_id` itself is unknown — a
        *parent* named in `covers_claim` that no longer exists in the ledger
        is silently skipped, not an error, so a stale edge left after a
        parent's id changes doesn't crash traversal (`validate` is the place
        to surface that as advisory debt, not this hot-path query)."""
        g = self.by_id(child_id)
        if g is None:
            raise GapParseError(f"unknown gap id: {child_id!r}")
        return [p for p in (self.by_id(pid) for pid in g.covers_claim) if p is not None]


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
