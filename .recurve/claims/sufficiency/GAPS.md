# sufficiency — the decomposition-cut arbiter, probed

> `recurvelib/analysis/sufficiency.py` + the `covers_claim` DAG edge on `Gap`
> (`docs/plans/autonomous_solver.md` §1): does a proposed cut's ASSEMBLY —
> "leaves imply goal" — get generated and gated correctly? Run
> `./recurve --config recurve.toml matrix --gate` and believe the gate.
>
> SUFF-6/7 guard two bugs found empirically while re-deriving the REAL, already-closed
> `SUB-PROD-YOUNG` in navier_stokes with `loop/solver.py` (a code-review-prompted
> validation of the Phase 3 acceptance run) — the first time `sufficiency_ok` was pointed
> at an already-ledgered claim instead of a fresh one.

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

## SUFF-6 — the scaffold writer refuses a case-colliding assembly_id

`write_lean_assembly_scaffold` refuses (raises) before writing anything when
`cut.assembly_id`'s probe path collides, case-insensitively, with a
DIFFERENT existing claim's real probe path — checked unconditionally, not
just on an actually-case-insensitive filesystem, so the guard is uniform
rather than a platform-dependent trap. Writing over `cut.assembly_id`'s OWN
existing files (an intentional re-derivation — SUFF-7) is not flagged; only
a collision with SOME OTHER claim is. Found empirically: on macOS's default
case-insensitive-but-preserving filesystem, re-deriving `SUB-PROD-YOUNG`
under a differently-cased assembly_id silently overwrote a real, tracked
claim's probe/check/trap files before this guard existed. Negative space: a
scaffold writer with no collision check, that clobbers a different claim's
real probe file, must turn the probe RED.

## SUFF-7 — `sufficiency_ok` promotes an already-ledgered claim on fresh GREEN

When `cut.assembly_id` is ALREADY a real row in `gaps.yaml` (re-deriving or
re-checking an existing claim, not arming a fresh draft), a fresh GREEN
measurement rewrites that row's `status` to `closed` directly —
`run_baseline` only ever processes `gaps.draft.yaml`, so a pre-existing row
is otherwise invisible to it regardless of what a fresh probe says. Found
empirically the same way as SUFF-6: `sufficiency_ok` returned `ok=True` for
the real, already-ledgered `SUB-PROD-YOUNG-ENORM` while its on-disk ledger
status silently stayed `open`. Negative space: a `sufficiency_ok` that
reports `ok=True` on an already-ledgered gap's fresh GREEN without rewriting
its ledger status must turn the probe RED.
