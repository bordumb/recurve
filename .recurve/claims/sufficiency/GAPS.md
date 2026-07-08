# sufficiency — the decomposition-cut arbiter, probed

> `recurvelib/analysis/sufficiency.py` + the `covers_claim` DAG edge on `Gap`
> (`docs/plans/autonomous_solver.md` §1): does a proposed cut's ASSEMBLY —
> "leaves imply goal" — get generated and gated correctly? Run
> `./recurve --config recurve.toml matrix --gate` and believe the gate.

## Conventions

`missing-surface` claims about `recurvelib.analysis.sufficiency` and the
`covers_claim` edge on `recurvelib.core.model.Gap`/`Ledger`, `reads: none` —
each probe exercises the pure generation/graph logic directly (no Lean, no
`lake`; the end-to-end Lean path is exercised separately by the Phase 1
acceptance run against a scratch navier_stokes copy, not by this suite).

## SUFF-1 — the pin call threads explicit free variables before hypotheses

`_check_source`'s call line applies the assembly theorem to `cut.explicit_args`
(names of any EXPLICIT `variable`s the goal/leaves close over, e.g. `a b` for
`variable (a b : E → ℂ)`) BEFORE the leaves' hypothesis names, in declaration
order — both the real theorem module and the check's `example` independently
auto-generalize a free explicit `variable` as a leading parameter (they are
separate files), so the pin must supply it by name or Lean reports a type
mismatch trying to unify a hypothesis against the variable's slot. Negative
space: a generator that omits `explicit_args` from the call (the exact bug
this claim guards — found empirically: `Check.lean:18:2: error: Type
mismatch` cutting the Hˢ crux's Route-B squared-lintegral step) must turn the
probe RED.

## SUFF-2 — the check file never inlines the assembly theorem

`_check_source`'s output contains no `theorem <name>` or `def <name>`
declaration of the assembly's own `theorem_name` — only a bare `example :=
<name> args` statement pin. This is what lets the shared `_lean_probe.sh`
trap-splice mechanism work unmodified: a trap fixture redefines `<name>` with
`sorry` standalone, and the check file (import-stripped) is appended after
it, so the trap's sorried definition is the only one left standing. Negative
space: a generator that defines the theorem inline in the check file (so
`<name>` is declared twice once spliced after a trap) must turn the probe RED.

## SUFF-3 — the trap shares the real theorem's exact signature

`_trap_source` and `_theorem_source` render byte-identical hypotheses blocks
and goal statements for the same `Cut` — they differ ONLY in the proof body
(`:= by sorry` vs. the real proof). This is required for the trap-splice
composition to even elaborate: the check's `example` is typed against ONE
signature, so the sorried definition standing in for the real one after
splicing must match it exactly. Negative space: a generator whose trap
signature drifts from the real theorem's (e.g. a hypothesis clause dropped
or reordered) must turn the probe RED.

## SUFF-4 — a claim cannot name itself as its own decomposition parent

`Gap.parse` rejects a draft/ledger entry whose `covers_claim` names its own
`id` — a claim being listed as a leaf of itself is a malformed DAG edge, not
a decomposition. Negative space: a parser that accepts `covers_claim:
[<own id>]` silently (constructing a self-loop) must turn the probe RED.

## SUFF-5 — `children_of` / `parents_of` invert each other over `covers_claim`

For a ledger where leaf gaps declare `covers_claim: [PARENT]`,
`Ledger.children_of(PARENT)` returns exactly those leaves (in ledger order),
and `Ledger.parents_of(leaf_id)` returns exactly `[PARENT]` for each — the
two queries are inverses over the same edge set, and a gap with no
`covers_claim` yields an empty `parents_of`. Negative space: a `children_of`
that also returns gaps whose `covers_claim` names a DIFFERENT parent (an
edge-selectivity bug) must turn the probe RED.
