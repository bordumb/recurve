"""Adversary/Governor: the two new pluggable review ports (`docs/plans/ablation-infra.md` AI1).

Completes the intention `runtime.py`'s own module docstring already states —
"the actor that proposes diffs and the adversary that red-teams claims are
pluggable agents behind protocols" — extended to the run-level governor R5
also needs. `World`, `Actor`, `capture()`, `within_boundary()`, and
`guarded_propose()` in `recurvelib.loop.runtime` are untouched by this
module: nothing here imports or mutates them.

Neither new port can certify a claim GREEN directly. `Adversary.review`
returns an `AdversaryVerdict` whose only shapes are "no objection" or "here is
a proposed counterexample" — a PROPOSAL the existing `capture()` rule
(`runtime.py`) still independently validates, exactly like any other trap.
`Governor.audit` returns a `GovernorVerdict` whose only shapes are cleared,
veto (a reason per claim), or pending (AI6's async human tier) — a veto never
mutates ledger state itself; turning it into a captured trap on the vetoed
claim (R5) is the calling loop's job, not this port's.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Protocol

# Field names that would let a verdict smuggle a direct certification past
# capture() — used by both the dataclasses below (they must never grow one)
# and by the anti-bypass structural check any adapter's verdict type is held
# to (AB-1's trap).
_FORBIDDEN_BYPASS_FIELDS = frozenset({"certified", "closed", "green", "status", "verdict_override"})


@dataclass(frozen=True)
class AdversaryVerdict:
    """`no_objection()`, or `proposed_trap(fixture, rationale)` — a proposal
    for `capture()` to independently judge. There is no third shape and no
    field that certifies anything; `is_clean` is the only query this type
    answers."""

    objection: tuple[str, str] | None = None  # (fixture_path, rationale), or None

    @property
    def is_clean(self) -> bool:
        return self.objection is None

    @staticmethod
    def no_objection() -> "AdversaryVerdict":
        return AdversaryVerdict(objection=None)

    @staticmethod
    def proposed_trap(fixture: str, rationale: str) -> "AdversaryVerdict":
        return AdversaryVerdict(objection=(fixture, rationale))


@dataclass(frozen=True)
class GovernorVerdict:
    """`cleared()`, `veto({claim_id: reason})`, or `pending_human_signoff()`
    (AI6 — the loop suspends cleanly rather than busy-waiting). A veto's
    reason is exactly what R5 requires to become a captured trap on the
    vetoed claim before the run may honor it — never a bare rejection."""

    vetoes: dict | None = None      # {claim_id: reason}, or None when clear/pending
    pending: bool = False           # AI6: awaiting a verified human attestation

    @property
    def is_clear(self) -> bool:
        return not self.pending and not self.vetoes

    @staticmethod
    def cleared() -> "GovernorVerdict":
        return GovernorVerdict(vetoes=None, pending=False)

    @staticmethod
    def veto(reasons: dict) -> "GovernorVerdict":
        return GovernorVerdict(vetoes=dict(reasons), pending=False)

    @staticmethod
    def pending_human_signoff() -> "GovernorVerdict":
        return GovernorVerdict(vetoes=None, pending=True)


class Adversary(Protocol):
    """A pluggable, decorrelated reviewer. Given a claim's committed
    artifacts (never the acting agent's live session), it either finds
    nothing, or proposes a counterexample for the EXISTING capture rule to
    independently validate — this port never certifies anything itself;
    `capture()` still does that."""

    def review(self, claim) -> AdversaryVerdict: ...


class Governor(Protocol):
    """A pluggable, superseding check on a cycle's decision to report
    STOP_SUCCESS. Given the cycle's newly-green claims as committed
    artifacts, plus a fresh-checkout re-execution capability, it clears the
    batch or vetoes specific claims with a reason."""

    def audit(self, cycle) -> GovernorVerdict: ...


def has_bypass_field(verdict_type: type) -> str | None:
    """Structural anti-bypass check: does this dataclass type carry any field
    name that could let an adapter certify a claim directly (bypassing
    `capture()`)? Returns the offending field name, or None if clean. Applies
    to any verdict type — the real ones above, or a candidate replacement —
    which is what makes this a reusable guard rather than a one-off
    assertion about today's two types."""
    try:
        names = {f.name for f in fields(verdict_type)}
    except TypeError:
        return None  # not a dataclass — nothing to check
    hit = names & _FORBIDDEN_BYPASS_FIELDS
    return sorted(hit)[0] if hit else None
