"""The agent runtime: the autonomous burndown loop spine (docs/plans/agent-runtime.md, steps A1-A6).

Wires the built sensors and judges (controller, completeness, fidelity, admission) into a loop. Everything
here is the DETERMINISTIC spine; the actor that proposes diffs and the adversary that red-teams claims are
pluggable agents behind protocols. The loop's safety comes from this spine — it measures instead of trusting
the actor (A1), senses real uncovered work and divergence (A2/A3), keeps the actor off the referee surface
(A4), only captures discriminating traps (A5), and never reaches an actor on a non-ADMIT contract (A6) — not
from the actor's competence.
"""
from __future__ import annotations

import posixpath
from typing import Protocol

from recurvelib.admission import admitted
from recurvelib.completeness import completeness_report
from recurvelib.controller import Progress, Verdict, decide
from recurvelib.fidelity import divergent
from recurvelib.measured import covered_by


class World(Protocol):
    """The target under burndown, as the loop sees it. The loop only measures and mutates through this."""

    def gate(self) -> Progress: ...
    def apply(self, diff) -> None: ...
    def checkpoint(self): ...
    def restore(self, snapshot) -> None: ...


class Actor(Protocol):
    """A pluggable coding agent: given the contract, one item, and failing evidence, it returns a diff."""

    def propose(self, contract, item, evidence): ...


# --- A6: the actor adapter guard -------------------------------------------------------------------------

def guarded_propose(actor, admission_report, contract, item, evidence):
    """Invoke the actor ONLY when the contract was ADMITted; a non-ADMIT contract never reaches an actor.

    Returns the actor's diff, or None if the contract is not admitted — so the loop never burns down a
    non-contract. Reuses :func:`recurvelib.admission.admitted` as the hard precondition.
    """
    if not admitted(admission_report):
        return None
    return actor.propose(contract, item, evidence)


# --- A4: the write boundary ------------------------------------------------------------------------------

def within_boundary(diff_paths, target_root: str, referee_roots) -> bool:
    """True iff every path in the diff is under ``target_root`` and under none of ``referee_roots``.

    The actor may change the target tree but never the referee surface (claims/probes/traps/gate config) —
    the structural guarantee that an autonomous actor cannot weaken the test it is graded by.
    """
    referee_roots = tuple(referee_roots)
    for raw in diff_paths:
        if posixpath.isabs(raw):
            return False                          # an absolute path escapes the target tree
        p = posixpath.normpath(raw)
        if p == ".." or p.startswith("../"):
            return False                          # a normalized path that climbs above the target tree
        if not p.startswith(target_root):
            return False
        for r in referee_roots:
            rr = r.rstrip("/")                       # match whole path components, not a bare prefix
            if p == rr or p.startswith(rr + "/"):    # the referee root itself, or something under it
                return False
    return True


# --- A5: the capture rule --------------------------------------------------------------------------------

def capture(trap_red_on_wrong: bool, trap_green_on_real: bool) -> bool:
    """The capture rule: an adversary's proposed trap is accepted only if it is RED on the wrong
    implementation AND GREEN on the real one — i.e. it discriminates. A trap that does not catch the bug, or
    that breaks the real code, is not evidence and is rejected.
    """
    return trap_red_on_wrong and trap_green_on_real


# --- A2 + A3: Sense --------------------------------------------------------------------------------------

def sense(gate_counts, surface, covered_ids, goal_counterexamples, deferred_ids=()):
    """Assemble the measured Progress vector and the ranked frontier from gate + completeness + fidelity.

    ``gate_counts`` is a mapping with ``open``/``regressed``/``broken`` from the probe gate. The completeness
    half (A2) supplies ``uncovered`` and the frontier; the fidelity half (A3) supplies ``divergent``. Returns
    ``(Progress, frontier)``. Nothing here reads an actor's self-report — every field is measured.
    """
    report = completeness_report(surface, covered_ids, deferred_ids)
    progress = Progress(
        open=gate_counts.get("open", 0),
        regressed=gate_counts.get("regressed", 0),
        broken=gate_counts.get("broken", 0),
        uncovered=report.uncovered,
        divergent=divergent(goal_counterexamples),
    )
    return progress, report.frontier


def sense_measured(gate_counts, surface, exercises, goal_counterexamples, deferred_ids=()):
    """Sense with **measured** coverage: derive the covered set by tracing each exercise, then assemble the
    Progress vector — so the frontier reflects what the probes actually *run*, not what a claim declares.

    This is the auto-wiring of measured coverage into the gate: ``covered_by`` traces every exercise (a claim's
    probe body) to the surface points it executes, and that measured covered set is what feeds ``sense`` — a
    point declared-covered but never exercised stays on the frontier.

    Args:
        gate_counts: Mapping with ``open``/``regressed``/``broken`` from the probe gate.
        surface: Iterable of SurfacePoint — the full claimable surface.
        exercises: Iterable of zero-argument callables — one per claim/probe.
        goal_counterexamples: Iterable of GoalCounterexample (the fidelity signal).
        deferred_ids: Iterable of surface ids explicitly deferred.

    Returns:
        ``(Progress, frontier)`` — the Progress vector with a *measured* ``uncovered``, and the frontier.
    """
    surface = list(surface)
    covered = covered_by(exercises, {p.id for p in surface})
    return sense(gate_counts, surface, covered, goal_counterexamples, deferred_ids)


# --- A1: the minimal closed loop -------------------------------------------------------------------------

def run(world, actor, admission_report, contract, max_cycles: int = 64):
    """The minimal closed loop: Sense -> decide -> Act -> record, with revert-to-last-green.

    The verdict is a pure function of ``world.gate()`` — the actor's output is applied as a diff and the world
    is re-measured; the actor's word is never an input to the decision. The contract must be ADMITted (A6) or
    the loop refuses to start.

    Returns ``(Verdict, history)``, or ``(None, [])`` if the contract was not admitted.
    """
    if not admitted(admission_report):
        return None, []
    history: list[Progress] = []
    last_green = world.checkpoint()
    for _ in range(max_cycles):
        progress = world.gate()                 # Sense: measured, never the actor's word
        history.append(progress)
        verdict = decide(history)               # Decide: deterministic controller
        if verdict is Verdict.STOP_SUCCESS:
            return verdict, history
        if verdict is Verdict.STOP_REVERT:
            world.restore(last_green)            # revert to the last sound floor
            return verdict, history
        if progress.open == 0 and progress.regressed == 0 and progress.broken == 0:
            last_green = world.checkpoint()      # probes pass here -> a floor to revert to
        diff = actor.propose(contract, None, progress)   # Act
        world.apply(diff)
    return Verdict.CONTINUE, history
