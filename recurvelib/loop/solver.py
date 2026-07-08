"""The move-typed recursion (`docs/plans/autonomous_solver.md` §2.1, §2.5): given a root
obligation, close it end-to-end with zero human turns between leaves.

Every move's output is confirmed the same way Phase 1 already gates a hand-written cut:
`sufficiency_ok` (`analysis/sufficiency.py`). This module adds no new arbiter — it is pure
orchestration around that one gated primitive:

  - **REFUTE**, tried first (cheap — falsify before investing): `ctx.refute_attempt(node_id,
    ctx)` returns `True` when the node's CURRENT framing is known-false or ill-posed. A
    refuted node is not closed or decomposed — `ctx.restate_attempt` either supplies a
    corrected node id to recurse into (§2.1's `restate_or_abandon`), or the node is
    abandoned to the frontier.
  - **CLOSE** a node directly: `ctx.close_attempt(node_id, ctx)` returns a `Cut` with no
    leaves — a bare proof term — when one is already known. `Cut.leaves=()` is a *direct*
    proof; there is no separate "close" code path in `sufficiency.py`, because a proof from
    zero hypotheses is definitionally the same "does `assembly_proof` prove `goal_statement`"
    question `sufficiency_ok` already answers.
  - **DISCOVER**, for `∃`-shaped nodes with a registered proxy (§2.4): `ctx.discover_attempt`
    runs a search (`fansearch.campaign.run_campaign`) and promotes a gate-confirmed candidate
    (`fansearch.promote.promote_candidate`) into a CLOSED leaf, or surfaces the frontier on a
    dry search. `analysis/shape.py:goal_shape` and "does this node have a proxy" are exactly
    the caller's business inside this one callable — `solve` itself stays domain-agnostic and
    just trusts `None` to mean "not applicable here."
  - **DECOMPOSE** a node: `ctx.cut_proposer(node_id, ctx)` returns a `Cut` with 1+ leaves.
    Its assembly is gated exactly like Phase 1 (leaves as HYPOTHESES); once gated GREEN, each
    leaf recurses through `solve`'s own `step`.
  - **Root-completion** (§2.5): when a leaf closes, `close_upward` walks `covers_claim` to
    find any parent whose *every* child (real leaves **and** the assembly itself — the
    assembly is a leaf too, per §1.3) is now closed, and gates the FINAL, unconditional proof
    — the assembly applied to the leaves' own (now-real) theorems instead of hypotheses. This
    is ledger-driven, not call-stack-driven: it fires regardless of how a leaf came to close,
    which is what lets a root many levels up eventually close from nothing but leaf-level
    events.
  - **Frontier**, when no move applies (or the budget is spent): the node's precise open
    statement is surfaced — parked (`loop/parked.py:ParkedStore`) when `ctx.parked_root` is
    set — the exact socket a human idea or a fitness search plugs into. Never automated.

`close_attempt`/`cut_proposer`/`discover_attempt`/`refute_attempt`/`restate_attempt` are the
pluggable "does the math" strategy (`claimify`-style proposer, per §1.4) — this module
supplies none of its own beyond `analysis/shape.py`'s syntactic shape check. A caller wires
in whatever produces `Cut`s or search outcomes (a hand-authored registry, as the acceptance
tests do; eventually an LLM- or heuristic-backed proposer); `solver.py` only owns the
recursion, the cost order, the tractability ordering, the budget, and the gate-mediated
bookkeeping. Every pluggable hook defaults to `None` (off) — a caller that only wires
`close_attempt`/`cut_proposer` (Phase 2's scope) sees no behavior change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from recurvelib.analysis.sufficiency import Cut, Leaf, sufficiency_ok
from recurvelib.core.config import Config
from recurvelib.core.model import Status, load_ledger
from recurvelib.loop.controller import Progress, Verdict, decide
from recurvelib.loop.parked import ParkedStore


class Move(Enum):
    """docs/plans/autonomous_solver.md §2.1 — the cost order `solve` tries them in:
    REFUTE, CLOSE, DISCOVER, DECOMPOSE, then FRONTIER (not a move; "nothing applied")."""

    REFUTE = "refute"
    CLOSE = "close"
    DISCOVER = "discover"
    DECOMPOSE = "decompose"
    RESTATE = "restate"


CutProposer = Callable[[str, "SolveContext"], "Cut | None"]
RefuteAttempt = Callable[[str, "SolveContext"], bool]
RestateAttempt = Callable[[str, "SolveContext"], "str | None"]
DiscoverAttempt = Callable[[str, "SolveContext"], "bool | None"]


@dataclass
class Budget:
    """docs/plans/autonomous_solver.md §2.3 — checked before `solve` spends effort on each
    obligation, so a misdirected leg costs at most one budget unit rather than an unbounded
    search. Both caps are optional; the default (neither set) never exhausts, so a caller
    that doesn't pass a budget sees no behavior change from Phase 2."""

    max_seconds: float | None = None
    max_moves: int | None = None
    _moves_spent: int = field(default=0, repr=False)
    _start: float = field(default_factory=time.monotonic, repr=False)

    def spend_move(self) -> None:
        self._moves_spent += 1

    def exhausted(self) -> bool:
        if self.max_moves is not None and self._moves_spent >= self.max_moves:
            return True
        if self.max_seconds is not None and (time.monotonic() - self._start) >= self.max_seconds:
            return True
        return False


@dataclass(frozen=True)
class SolveContext:
    """Everything one `solve` recursion needs, threaded unchanged through every `step`.

    `close_attempt`/`cut_proposer`/`discover_attempt`/`refute_attempt`/`restate_attempt` are
    the only math-aware inputs — see the module docstring. All take a bare gap id (not a
    `Gap`): a proposed leaf need not exist as a ledger row yet, so `solve` never requires one
    to look it up before asking "can this be closed, cut, discovered, or refuted?".
    `refute_attempt`/`restate_attempt`/`discover_attempt` default to `None` — that move is
    simply never tried, so a Phase 2 caller wiring only `close_attempt`/`cut_proposer` is
    unaffected.

    `sufficiency_check` defaults to the real `sufficiency_ok` (real Lean, real `lake`, real
    gate) — the same swap-the-verifier seam `core/probe.py:ProbeRunner` already gives the
    rest of the loop. Overriding it with an in-memory fake is what lets a dogfooding suite
    exercise `solve`'s own recursion / tractability ordering / root-completion propagation
    in pure Python, fast, with no Lean toolchain in the loop — see
    `.recurve/claims/solver/GAPS.md`.

    `parked_root`, when set, is the project root `loop/parked.py:ParkedStore` writes
    `.recurve/parked.yaml` under — a node `solve` surfaces to the frontier is parked there
    with the reason it couldn't move forward, so an unattended run leaves a reconstructable
    record of exactly where the known part of the problem ends (§2.3, §2.7)."""

    config: Config
    today: str
    close_attempt: CutProposer
    cut_proposer: CutProposer
    timeout_s: int = 300
    sufficiency_check: Callable[..., object] = sufficiency_ok
    refute_attempt: RefuteAttempt | None = None
    restate_attempt: RestateAttempt | None = None
    discover_attempt: DiscoverAttempt | None = None
    budget: Budget = field(default_factory=Budget)
    parked_root: Path | None = None


@dataclass(frozen=True)
class SolveResult:
    closed: tuple[str, ...]
    frontier: tuple[str, ...]
    trace: tuple[str, ...]


def order_by_tractability(leaves: tuple[Leaf, ...], ctx: SolveContext) -> list[Leaf]:
    """docs/plans/autonomous_solver.md §2.3, extended for cut-proposal time: leaves aren't
    ledger rows yet (they're only armed as `solve` recurses into them), so
    `analysis.triage.tractability` doesn't apply directly. The cheapest available signal at
    this point is the same one §2.2 uses for move availability: a leaf `close_attempt`
    already knows how to close directly is more tractable than one that still needs its own
    decomposition."""
    return sorted(leaves, key=lambda leaf: (0 if ctx.close_attempt(leaf.id, ctx) is not None else 1, leaf.id))


def _is_closed(gap_id: str, ctx: SolveContext) -> bool:
    gap = load_ledger(ctx.config).by_id(gap_id)
    return gap is not None and gap.status is Status.CLOSED


def _direct_root_cut(node_id: str, cut: Cut, ctx: SolveContext) -> Cut:
    """Once every leaf in `cut` is CLOSED, `node_id`'s goal follows unconditionally: apply
    the (already-GREEN) assembly to the leaves' own real theorems instead of hypotheses.
    Reuses `Cut`/`sufficiency_ok` wholesale — a leaves=() Cut IS a direct proof, so this
    needs no new Lean-generation code, only a proof term built from what closed each leaf.
    `assembly_id=node_id` is what makes this THE node's own closure, not another child of it
    (see `sufficiency.py`'s `_draft_entry_yaml` self-reference guard, added for this case)."""
    leaf_terms: list[str] = []
    leaf_imports: list[str] = []
    for leaf in cut.leaves:
        leaf_cut = ctx.close_attempt(leaf.id, ctx)
        if leaf_cut is None:
            raise ValueError(
                f"{leaf.id} is closed but close_attempt no longer explains how — "
                "a non-deterministic proposer breaks root-completion's replay"
            )
        # Parenthesized: a leaf's own term is itself a multi-token application
        # (`name arg1 arg2 …`) — left as bare tokens it would be parsed as more
        # arguments to the assembly instead of one grouped argument.
        leaf_terms.append("(" + " ".join((leaf_cut.theorem_name, *leaf_cut.explicit_args)) + ")")
        leaf_imports.append(leaf_cut.lean_module)
    proof = "exact " + " ".join((cut.theorem_name, *cut.explicit_args, *leaf_terms))
    return Cut(
        parent_id=cut.parent_id,
        goal_statement=cut.goal_statement,
        leaves=(),
        assembly_proof=proof,
        suite=cut.suite,
        lean_module=f"{cut.lean_module}Root",
        imports=(cut.lean_module, *leaf_imports, *cut.imports),
        opens=cut.opens,
        variables=cut.variables,
        explicit_args=cut.explicit_args,
        assembly_id=node_id,
    )


def _ready_to_assemble(cut: Cut, ctx: SolveContext) -> bool:
    """True iff every EXPECTED child of `cut` — its leaves AND its own assembly, which is a
    leaf too (§1.3) — is CLOSED. Checked against `cut_proposer`'s expected id set, not
    `ledger.children_of`: while `solve` is still arming leaves one at a time, `children_of`
    only sees whichever ones have reached the ledger so far, so an early leaf closing would
    otherwise look (falsely) like "every child is closed" and fire a doomed assembly attempt
    before its siblings even exist. Harmless either way — a premature attempt just fails
    cleanly at the real gate — but this avoids the wasted, confusing attempt entirely."""
    expected = (*(l.id for l in cut.leaves), cut.assembly_id)
    return all(_is_closed(cid, ctx) for cid in expected)


def close_upward(closed_id: str, ctx: SolveContext, closed: list[str], trace: list[str]) -> None:
    """docs/plans/autonomous_solver.md §2.5. Ledger-driven, not call-stack-driven: walks
    `covers_claim` from `closed_id` to find any parent whose children are now ALL closed
    (`_ready_to_assemble`), gates that parent's final unconditional proof, and recurses
    upward — this is what lets a root many levels above a single leaf eventually close from
    nothing but that leaf's own closure event, regardless of which `step` call closed it."""
    ledger = load_ledger(ctx.config)
    leaf = ledger.by_id(closed_id)
    if leaf is None:
        return
    for parent_id in leaf.covers_claim:
        if _is_closed(parent_id, ctx):
            continue
        cut = ctx.cut_proposer(parent_id, ctx)
        if cut is None:
            continue  # the parent's own decomposition isn't (re)constructible — leave it frontier
        if not _ready_to_assemble(cut, ctx):
            continue
        final = _direct_root_cut(parent_id, cut, ctx)
        result = ctx.sufficiency_check(final, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
        trace.append(f"assemble({parent_id}) via close_upward: {result.detail}")
        if result.ok:
            if parent_id not in closed:
                closed.append(parent_id)
            close_upward(parent_id, ctx, closed, trace)


def solve(root_id: str, ctx: SolveContext) -> SolveResult:
    """One recursive step per obligation (§2.1): REFUTE, CLOSE, DISCOVER, DECOMPOSE, in cost
    order, else surface the frontier. Recurses to every leaf and lets `close_upward`
    propagate closures back to `root_id` — one call, zero human turns in between."""
    closed: list[str] = []
    frontier: list[str] = []
    trace: list[str] = []

    def surface(gap_id: str, reason: str) -> None:
        if gap_id not in frontier:
            frontier.append(gap_id)
        trace.append(f"frontier({gap_id}): {reason}")
        if ctx.parked_root is not None:
            ParkedStore(ctx.parked_root).park(gap_id, reason, ctx.today)

    def step(gap_id: str) -> bool:
        if _is_closed(gap_id, ctx):
            return True
        if ctx.budget.exhausted():
            surface(gap_id, "budget exhausted")
            return False
        ctx.budget.spend_move()

        if ctx.refute_attempt is not None and ctx.refute_attempt(gap_id, ctx):
            trace.append(f"{Move.REFUTE.value}({gap_id}): current framing is refuted")
            restated_id = ctx.restate_attempt(gap_id, ctx) if ctx.restate_attempt else None
            if restated_id is not None:
                trace.append(f"{Move.RESTATE.value}({gap_id} -> {restated_id})")
                return step(restated_id)
            surface(gap_id, "refuted — no restatement available, abandoned")
            return False

        direct = ctx.close_attempt(gap_id, ctx)
        if direct is not None:
            result = ctx.sufficiency_check(direct, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
            trace.append(f"{Move.CLOSE.value}({gap_id}): {result.detail}")
            if result.ok:
                if gap_id not in closed:
                    closed.append(gap_id)
                close_upward(gap_id, ctx, closed, trace)
                return True

        if ctx.discover_attempt is not None:
            outcome = ctx.discover_attempt(gap_id, ctx)
            if outcome is not None:
                if outcome:
                    trace.append(f"{Move.DISCOVER.value}({gap_id}): gate-confirmed candidate promoted")
                    if gap_id not in closed:
                        closed.append(gap_id)
                    close_upward(gap_id, ctx, closed, trace)
                    return True
                trace.append(f"{Move.DISCOVER.value}({gap_id}): search dry")
                surface(gap_id, "discover search dry")
                return False

        cut = ctx.cut_proposer(gap_id, ctx)
        if cut is not None:
            result = ctx.sufficiency_check(cut, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
            trace.append(f"{Move.DECOMPOSE.value}({gap_id} -> {[l.id for l in cut.leaves]}): {result.detail}")
            if result.ok:
                for child in order_by_tractability(cut.leaves, ctx):
                    step(child.id)
                if _is_closed(gap_id, ctx):
                    if gap_id not in closed:
                        closed.append(gap_id)
                    return True

        surface(gap_id, "no move applies")
        return False

    step(root_id)
    return SolveResult(closed=tuple(closed), frontier=tuple(frontier), trace=tuple(trace))


def run_to_completion(root_id: str, ctx: SolveContext, max_cycles: int = 10) -> tuple[Verdict, list[Progress], SolveResult]:
    """docs/plans/autonomous_solver.md §2.3 — reuse `loop/controller.py:decide`, never
    reimplement halt logic. One `solve()` call is a single deterministic pass over the
    obligation tree; it does not retry a frontier node within itself. This wrapper is for
    the OUTER loop: re-invoke `solve` (e.g. after a human resolves a frontier node's root
    cause, or a proxy registry gains a new domain) and measure whether the frontier is
    actually shrinking, so a run that stops making progress halts honestly — via `decide`'s
    own no-improvement rule — rather than spinning on an unchanged frontier forever.

    Progress is measured directly from `solve`'s own result: `uncovered=len(frontier)` is
    the completeness signal `decide` needs; `open`/`regressed`/`broken` stay 0 because
    `solve`'s bookkeeping already IS the gate-mediated truth for the obligations it knows
    about (each move is confirmed by `sufficiency_check` before counting as closed) — there
    is no separate, unmeasured "claimed done" state for `decide` to catch here the way there
    is for an actor proposing diffs blind (`loop/runtime.py:sense_measured`'s heavier
    surface-tracing is for that different loop shape).

    Returns `(verdict, history, last_result)` — `verdict` is `STOP_SUCCESS` (root closed),
    `STOP_REVERT` (no progress for `decide`'s window), or `CONTINUE` (max_cycles exhausted
    without either — the budget, not `decide`, is what should have capped this)."""
    history: list[Progress] = []
    result = SolveResult(closed=(), frontier=(), trace=())
    for _ in range(max_cycles):
        result = solve(root_id, ctx)
        history.append(Progress(open=0, regressed=0, broken=0, uncovered=len(result.frontier)))
        verdict = decide(history)
        if verdict in (Verdict.STOP_SUCCESS, Verdict.STOP_REVERT):
            return verdict, history, result
        if ctx.budget.exhausted():
            return Verdict.STOP_REVERT, history, result
    return Verdict.CONTINUE, history, result
