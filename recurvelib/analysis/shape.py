"""The goal-shape (∀/∃) detector (`docs/plans/autonomous_solver.md` §2.2) — one of three
cheap, mechanical signals the controller uses to pick a move, never a full elaboration:

  1. **Node logical shape** (this module). `∃ x, P x` (find a witness) points at DISCOVER;
     `∀ …`/an implication/a bare proposition (prove it) points at CLOSE/DECOMPOSE.
  2. **Signal availability** — DISCOVER needs a registered proxy for the node's domain;
     CLOSE/DECOMPOSE need library support to scout. Absent means that move is off the
     table — `loop/solver.py`'s pluggable `close_attempt`/`cut_proposer`/`discover_attempt`
     each return `None` when their move doesn't apply, which is where that signal lives.
  3. **Cheap-first, then prune** — cost order plus the gate; see `loop/solver.py:solve`.

This module owns only the first signal, over a claim's STATED goal text (its `smallest_fix`
target, a check file's pinned statement, or any other raw Lean-proposition string) — a
syntactic head-check, not a type-checker.
"""

from __future__ import annotations

import re

_EXISTENTIAL = re.compile(r"^\s*(∃|\\exists\b|Exists\b)")


def goal_shape(statement: str) -> str:
    """"∃" if `statement`'s head is an existential quantifier; "∀" otherwise (a universal,
    an implication, or a bare proposition — anything solve() should try to PROVE rather than
    find a witness for)."""
    return "∃" if _EXISTENTIAL.match(statement) else "∀"
