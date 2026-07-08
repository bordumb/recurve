"""Triage policy — lives in code, not in a runbook, so any new session is
re-entrant: `next` is identical on cycle 1 and cycle 20.

The ordering axis is VALUE, not gentleness: a wrong sculpt of anything except
`security-tradeoff` fails LOUD (RED probe / broken harness / failed build), so
the green gate is sufficient and size is no reason to defer it. The highest-
value work is auto-recommended FIRST.

The ONE exception is `security-tradeoff`: loosening what the target rejects
can pass every existing probe and still open a hole no probe tests — a green
gate is necessary but NOT sufficient. Those are "review-gated": workable, but
only through the adversarial-review protocol, never on a green gate alone.
"""

from __future__ import annotations

from recurvelib.core.config import Config
from recurvelib.core.model import Gap, GapClass, Ledger, Severity, Status

# Tiebreak among equal value: prefer duplication-collapsing, low-blast classes.
_CLS_TIEBREAK = {
    GapClass.BROKEN_ROUTE: 0, GapClass.WIRE_MISMATCH: 0, GapClass.MISSING_SURFACE: 1,
    GapClass.STAGING: 2, GapClass.FRICTION: 3, GapClass.SECURITY_TRADEOFF: 9,
}


def severity_rank(config: Config) -> dict[Severity, int]:
    """Value-first: lower rank = higher value = recommended sooner. The order
    comes from [triage] severity_order in recurve.toml."""
    rank: dict[Severity, int] = {}
    for i, name in enumerate(config.severity_order):
        try:
            rank[Severity(name)] = i
        except ValueError:
            pass  # config.load vetted shape; unknown names just never match
    return rank


def review_gated(g: Gap) -> bool:
    """Green gate is necessary-but-not-sufficient → needs adversarial review."""
    return g.gap_class is GapClass.SECURITY_TRADEOFF


def tractability(g: Gap) -> int:
    """Cheap, mechanical tractability signal (docs/plans/autonomous_solver.md §2.3): a gap
    already cut down to a leaf of an active decomposition (non-empty `covers_claim`) is a
    smaller, closer-to-done piece than an undecomposed item — rank it sooner. 0 for every
    gap outside a decomposition (the whole fleet, until covers_claim is actually used
    somewhere), so this is a pure additive tiebreak: it reorders nothing until a suite
    actually has leaves in flight."""
    return 0 if g.covers_claim else 1


def triage(ledger: Ledger, config: Config) -> tuple[list[Gap], list[Gap]]:
    """(auto, gated): open gaps sorted value-first, review-gated split out."""
    rank = severity_rank(config)
    open_gaps = [g for g in ledger.gaps if g.status is Status.OPEN]
    auto = sorted(
        [g for g in open_gaps if not review_gated(g)],
        key=lambda g: (rank.get(g.severity, 9), _CLS_TIEBREAK[g.gap_class], tractability(g), g.id),
    )
    gated = sorted(
        [g for g in open_gaps if review_gated(g)],
        key=lambda g: (rank.get(g.severity, 9), g.id),
    )
    return auto, gated


def lanes(ledger: Ledger, config: Config, n: int,
          exclude: set[str] | None = None) -> list[Gap]:
    """Up to n parallel lanes: each suite's highest-value workable gap, suites
    pairwise disjoint. Two lanes in one suite would sculpt the same ledger and
    prose — the scheduler, not the agents, guarantees they never can."""
    auto, _ = triage(ledger, config)
    picked: list[Gap] = []
    seen_suites: set[str] = set()
    for g in auto:
        if exclude and g.id in exclude:
            continue
        if g.suite in seen_suites:
            continue
        seen_suites.add(g.suite)
        picked.append(g)
        if len(picked) >= n:
            break
    return picked
