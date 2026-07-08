"""The move-typed recursion (`docs/plans/autonomous_solver.md` §2.1, §2.5): given a root
obligation, close it end-to-end with zero human turns between leaves.

Phase 2 scope only: `CLOSE` and `DECOMPOSE`. `REFUTE`/`DISCOVER`/`RESTATE` need the shape
detector (`analysis/shape.py`) and the fansearch wiring — that is Phase 3. `solve()` here
never has to guess a node's ∀/∃ shape; it just tries the two moves it has, in cost order,
and surfaces a `frontier` node when neither applies.

Every move's output is confirmed the same way Phase 1 already gates a hand-written cut:
`sufficiency_ok` (`analysis/sufficiency.py`). This module adds no new arbiter — it is pure
orchestration around that one gated primitive:

  - **CLOSE** a node directly: `ctx.close_attempt(node_id, ctx)` returns a `Cut` with no
    leaves — a bare proof term — when one is already known. `Cut.leaves=()` is a *direct*
    proof; there is no separate "close" code path in `sufficiency.py`, because a proof from
    zero hypotheses is definitionally the same "does `assembly_proof` prove `goal_statement`"
    question `sufficiency_ok` already answers.
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

`close_attempt`/`cut_proposer` are the pluggable "does the math" strategy (`claimify`-style
proposer, per §1.4) — this module supplies none of its own. A caller wires in whatever
produces `Cut`s (a hand-authored registry, as the acceptance test below does; eventually an
LLM- or heuristic-backed proposer); `solver.py` only owns the recursion, the ordering, and
the gate-mediated bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from recurvelib.analysis.sufficiency import Cut, Leaf, sufficiency_ok
from recurvelib.core.config import Config
from recurvelib.core.model import Status, load_ledger


class Move(Enum):
    """docs/plans/autonomous_solver.md §2.1. Only CLOSE/DECOMPOSE are wired in Phase 2;
    REFUTE/DISCOVER/RESTATE are declared here for API stability but `solve` never emits
    them yet — Phase 3 wires the shape detector and fansearch in beside these two."""

    CLOSE = "close"
    DECOMPOSE = "decompose"
    REFUTE = "refute"
    DISCOVER = "discover"
    RESTATE = "restate"


CutProposer = Callable[[str, "SolveContext"], "Cut | None"]


@dataclass(frozen=True)
class SolveContext:
    """Everything one `solve` recursion needs, threaded unchanged through every `step`.

    `close_attempt`/`cut_proposer` are the only math-aware inputs — see the module
    docstring. Both take a bare gap id (not a `Gap`): a proposed leaf need not exist as a
    ledger row yet, so `solve` never requires one to look it up before asking "can this be
    closed or cut?".

    `sufficiency_check` defaults to the real `sufficiency_ok` (real Lean, real `lake`, real
    gate) — the same swap-the-verifier seam `core/probe.py:ProbeRunner` already gives the
    rest of the loop. Overriding it with an in-memory fake is what lets a dogfooding suite
    exercise `solve`'s own recursion / tractability ordering / root-completion propagation
    in pure Python, fast, with no Lean toolchain in the loop — see
    `.recurve/claims/solver/GAPS.md`."""

    config: Config
    today: str
    close_attempt: CutProposer
    cut_proposer: CutProposer
    timeout_s: int = 300
    sufficiency_check: Callable[..., object] = sufficiency_ok


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
    """One recursive step per obligation (§2.1), Phase 2 scope: CLOSE, then DECOMPOSE, else
    surface the frontier. Recurses to every leaf and lets `close_upward` propagate closures
    back to `root_id` — one call, zero human turns in between."""
    closed: list[str] = []
    frontier: list[str] = []
    trace: list[str] = []

    def step(gap_id: str) -> bool:
        if _is_closed(gap_id, ctx):
            return True

        direct = ctx.close_attempt(gap_id, ctx)
        if direct is not None:
            result = ctx.sufficiency_check(direct, ctx.config, today=ctx.today, timeout_s=ctx.timeout_s)
            trace.append(f"{Move.CLOSE.value}({gap_id}): {result.detail}")
            if result.ok:
                if gap_id not in closed:
                    closed.append(gap_id)
                close_upward(gap_id, ctx, closed, trace)
                return True

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

        if gap_id not in frontier:
            frontier.append(gap_id)
            trace.append(f"frontier({gap_id}): no move applies")
        return False

    step(root_id)
    return SolveResult(closed=tuple(closed), frontier=tuple(frontier), trace=tuple(trace))
