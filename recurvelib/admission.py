"""The admission gate: is a goal gateable — can it become a faithful contract at all?

A goal is a set of **assertions**. An assertion is *probe-able* to the degree a falsifying check can be named
for it: it must be **falsifiable** (an observable pass/fail), have a **counterexample** (you can name what
"wrong" looks like), and have **bounded** scope (an enumerable surface). Whether a given natural-language
assertion meets each criterion is a *judgment* — supplied by a rater (an LLM, or a fixture in tests). This
module owns the deterministic **spine** around that judgment: the gateability metric, the per-assertion
diagnostic worklist, and the three-way verdict. The judgment plugs into the same seam as coverage and
fidelity; the verdict logic is fixed and itself gated, so the gate cannot quietly lower its own bar.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    """The admission verdict for a goal."""

    ADMIT = "ADMIT"
    REFUSE_AND_INTERVIEW = "REFUSE-AND-INTERVIEW"
    REFUSE_NOT_GATEABLE = "REFUSE-NOT-GATEABLE"


@dataclass(frozen=True)
class Assertion:
    """One assertion of a goal, with the rater's per-criterion findings.

    Args:
        id: Stable identifier.
        text: The assertion as the human stated it (for the diagnostic).
        falsifiable: There is an observable pass/fail (an oracle).
        has_counterexample: You can name what "wrong" looks like (a trap).
        bounded: The surface it touches is enumerable (so completeness is measurable).
    """

    id: str
    text: str
    falsifiable: bool
    has_counterexample: bool
    bounded: bool

    @property
    def probeable(self) -> bool:
        """Probe-able iff ALL three criteria hold — a missing oracle, counterexample, OR bound disqualifies."""
        return self.falsifiable and self.has_counterexample and self.bounded

    def gaps(self) -> list:
        """The named, falsifiable reasons this assertion is not yet probe-able — the interview worklist."""
        out = []
        if not self.falsifiable:
            out.append("no observable pass/fail (no oracle)")
        if not self.has_counterexample:
            out.append("no counterexample (cannot name what 'wrong' looks like)")
        if not self.bounded:
            out.append("unbounded scope (no enumerable surface)")
        return out


@dataclass(frozen=True)
class AdmissionReport:
    """The admission verdict plus the falsifiable diagnostic — never a bare score.

    Args:
        verdict: ADMIT / REFUSE_AND_INTERVIEW / REFUSE_NOT_GATEABLE.
        probeable: Count of probe-able assertions (the gateable spine).
        total: Total assertions.
        gateability: ``probeable / total`` — measured, not rated.
        worklist: ``((assertion_id, (gap, ...)), ...)`` for each not-yet-probe-able assertion.
        min_invariants: The spine size below which a goal is too thin to gate.
    """

    verdict: Verdict
    probeable: int
    total: int
    gateability: float
    worklist: tuple
    min_invariants: int


def gateability(assertions) -> float:
    """The share of assertions that are probe-able (``probeable / total``); ``0.0`` for an empty goal."""
    assertions = list(assertions)
    if not assertions:
        return 0.0
    return sum(1 for a in assertions if a.probeable) / len(assertions)


def worklist(assertions) -> tuple:
    """The interview worklist: each not-yet-probe-able assertion with its named gaps (never a probe-able one)."""
    return tuple((a.id, tuple(a.gaps())) for a in assertions if not a.probeable)


def admit(assertions, min_invariants: int = 2) -> AdmissionReport:
    """Decide whether a goal is gateable, with the diagnostic worklist.

    Verdict rules (a goal's *gateable spine* is its probe-able assertions):
      * ``REFUSE_NOT_GATEABLE`` — the spine is smaller than ``min_invariants``: too few stable invariants to
        gate honestly (creative/exploratory work — recommend not gating).
      * ``ADMIT`` — every assertion is probe-able (and the spine is large enough).
      * ``REFUSE_AND_INTERVIEW`` — a large-enough spine exists but some assertions are not yet probe-able;
        emit the worklist and interview to close them.

    Args:
        assertions: Iterable of Assertion (the rater's findings).
        min_invariants: Minimum probe-able assertions for a goal to be worth gating.

    Usage:
        report = admit(assertions)
        if report.verdict is Verdict.REFUSE_AND_INTERVIEW:
            for aid, gaps in report.worklist: ...  # interview each
    """
    assertions = list(assertions)
    total = len(assertions)
    spine = sum(1 for a in assertions if a.probeable)
    wl = worklist(assertions)

    if spine < min_invariants:
        verdict = Verdict.REFUSE_NOT_GATEABLE
    elif spine == total:
        verdict = Verdict.ADMIT
    else:
        verdict = Verdict.REFUSE_AND_INTERVIEW

    return AdmissionReport(
        verdict=verdict,
        probeable=spine,
        total=total,
        gateability=(spine / total if total else 0.0),
        worklist=wl,
        min_invariants=min_invariants,
    )


class InterviewVerdict(Enum):
    """The next move in the admission interview."""

    CONTINUE = "CONTINUE"
    ADMIT = "ADMIT"
    ESCALATE = "ESCALATE"


def interview_step(history, max_rounds: int = 3) -> InterviewVerdict:
    """Decide the next move in the interview (G3), from the per-round assertion states (most recent last).

    The interview turns vague assertions into probe-able ones by asking, for each, "what would *wrong* look
    like?" Each entry in ``history`` is the goal's assertions as they stood after that round (a rater applies
    the human's answers — that judgment is the pluggable agent part). This is the interview's stopping rule
    (``admission-gate.md §4``) — the same shape as the burndown controller, so the interview cannot run
    forever:

      * ``ADMIT``    — the latest round is fully probe-able; the goal is now a contract.
      * ``ESCALATE`` — ``max_rounds`` reached with no net reduction in the un-probe-able set: the human cannot
        name the checks, so the goal is genuinely not gateable — escalate, do not interview forever.
      * ``CONTINUE`` — otherwise; the un-probe-able set is shrinking, keep going.

    Args:
        history: Rounds in order, most recent last; each round is an iterable of Assertion.
        max_rounds: Window after which a non-shrinking un-probe-able set escalates.

    Usage:
        v = interview_step(rounds)  # -> InterviewVerdict.ADMIT / ESCALATE / CONTINUE
    """
    history = [list(round_) for round_ in history]
    if not history:
        return InterviewVerdict.CONTINUE
    remaining = [sum(1 for a in round_ if not a.probeable) for round_ in history]
    if remaining[-1] == 0:
        return InterviewVerdict.ADMIT
    if len(history) >= max_rounds:
        window = remaining[-max_rounds:]
        if window[-1] >= window[0]:
            return InterviewVerdict.ESCALATE
    return InterviewVerdict.CONTINUE


def admitted(report: AdmissionReport) -> bool:
    """The synthesis precondition (G4): a goal proceeds to synthesis only if it was ADMITted.

    A REFUSE verdict — vague (``REFUSE_AND_INTERVIEW``) or too thin (``REFUSE_NOT_GATEABLE``) — must never
    reach synthesis; letting one through would bypass the entire admission gate and burn down a non-contract.

    Usage:
        if admitted(admit(assertions)):
            synthesize(...)  # only an admitted goal becomes claims
    """
    return report.verdict is Verdict.ADMIT

