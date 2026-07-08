# PRD — the autonomous solver: decomposition, and a cohesive move-typed loop

> **So what? (in plain terms.)** Today the system can break a hard proof into pieces on its
> own — but a human still has to nudge it through those pieces one at a time ("continue,"
> "now the next one"), across sessions, by hand. This doc specifies the two things that
> remove the nudging and make it *one* organic process:
>
> **Part 1 — decomposition:** the ability to cut a goal into smaller pieces *and mechanically
> prove the pieces add up to the goal* (even before any piece is proved). That check is what
> lets the system recurse on its own without hallucinating a plan whose parts don't actually
> imply the goal.
>
> **Part 2 — a cohesive loop with a controller:** one search that, at every open obligation,
> picks the *move* its shape calls for — prove it, cut it, discover a witness for it, or
> refute it — ranked by which piece is closest to done, confirmed by the same kernel, all the
> way to the root or to the exact edge of the unknown. There is no "which tool do I use"
> decision; the terrain picks the move.
>
> **What it unlocks:** *"solve this to completion, N leaves deep, unattended"* for the whole
> known part of a problem — and, for the unknown part, an honest, precise statement of exactly
> where the known part ends and an idea (or a fitness-guided search) has to take over.

> **Scope.** Supersedes `recursive_driver.md`/`decomposer.md`; folds in the fansearch
> relationship. This is the **inner** loop — given a root goal, solve it to completion; the
> campaign layer above it (which goal, human checkpoints *between* campaigns) is
> `automation_roadmap.md`, and the stop/spend brain it reuses is `stopping-controller.md` /
> `separation-of-refereeing.md`. It changes nothing about how a single claim is certified:
> every move's output is confirmed by the existing gate. **Written pre-launch.**

---

# 0 · The codebase map — what exists, what to extend, what is new

A zero-context implementer starts here. Every path is under `recurvelib/`. **Most of the loop
already exists**; the new surface is small and named.

| Concern | Where it lives | Status |
|---|---|---|
| The gate (run every probe, aggregate verdicts) | `core/conformance.py:run_matrix`, `core/probe.py` (`Outcome`, `ProbeResult`, `run_traps`) | **exists — reuse** |
| The verifier *port* (swap Lean ↔ `cargo` ↔ tests) | `core/probe.py:ProbeRunner` (Protocol), `ShellProbeRunner`, `CachingProbeRunner`; `core/protocols.py` | **exists — reuse** |
| Arm drafts RED-first → real claims | `core/baseline.py:run_baseline(config, suite, today) -> (outcomes, ok)` | **exists — reuse** |
| Decompose a spec → falsifiable draft claims | `analysis/claimify.py` | **exists — extend** (goal→leaves **+ assembly**) |
| Value ranking behind `recurve next` | `analysis/triage.py:triage(ledger, config) -> (auto, gated)` | **exists — extend** (add tractability to the sort key) |
| Stopping brain (continue / stop / revert / pivot) | `loop/controller.py:decide(history, k, governor_status) -> Verdict`; `Progress(open, regressed, broken, uncovered, divergent)` | **exists — reuse**; `uncovered` = frontier size |
| Progress measured *from the gate* | `loop/runtime.py:sense_measured(gate_counts, surface, exercises, goal_counterexamples, …) -> Progress` | **exists — reuse** |
| Loop / cycle orchestration | `loop/run.py:build_run(…)`, `loop/cycle.py:write_cycle_plan(…)` | **exists — wrap** |
| Discover move (proxy search → gate-confirm → promote) | `fansearch/campaign.py:run_campaign(cfg, domain, ns_repo, budget_seconds, …)`, `fansearch/promote.py:promote_candidate(…)`, `adapters/proxy.py:PROXY_ADAPTERS` | **exists — call as a move** |
| Ledger model (`Gap`, `Status{OPEN,SCULPTING,CLOSED}`, `Ledger`) | `core/model.py` | **extend** — add the parent edge (§1.3) |
| **The decomposition parent→child edge** | `core/model.py:Gap` (today only `covers` = *GAPS.md prose anchors*, **not** a claim edge) | **NEW — the one required schema change** |
| **The sufficiency harness** | `analysis/sufficiency.py` | **NEW** |
| **Move dispatch + the obligation recursion** | `loop/solver.py` | **NEW** |
| **The goal-shape (`∀`/`∃`) detector** | `analysis/shape.py` | **NEW** |

Net: five new/edited things — the parent edge, `sufficiency.py`, `solver.py`, `shape.py`, and
sort-key + `claimify` extensions. Everything else is wiring over code that already runs.

---

# Part 1 — Build decomposition

Decomposition is the atomic recursive move: cut an obligation `P` into leaves `L₁…Lₙ` plus an
**assembly** that derives `P` from them. Build it first and standalone — it carries the one
mechanical guarantee the whole autonomous story rests on.

## 1.1 The one thing that is mechanically checkable: sufficiency

"Is this the right decomposition?" factors into two questions; exactly one has an arbiter:

- **Sufficiency — arbitered.** *Do the leaves imply the goal?* Author the assembly claim that
  proves `P` **from the leaves as hypotheses**; if it is **kernel-clean GREEN**, then
  *"L₁ ∧ … ∧ Lₙ ⟹ P"* is a kernel-verified fact — the cut is logically valid, by the same
  gate that certifies everything else. **A cut is accepted exactly when its assembly goes
  GREEN.** No new arbiter, no self-grading.
- **Provability & taste — un-arbitered.** *Are the leaves themselves true/closable? Is the cut
  sensible?* No oracle. Adjudicated later by the loop *trying* to close each leaf (a false leaf
  fails and parks) and, at the boundary, by a human.

This is not hypothetical. In the live Navier–Stokes run, the continuous-Minkowski assembly
lemma took the slice family and the a.e. Bochner identification *as hypotheses* and proved the
bound — a GREEN certifying the cut before any leaf was proved. That lemma **was** the check.

## 1.2 What to build: `analysis/sufficiency.py`

The assembly claim is armed and gated exactly like any claim — this is why it is trustworthy on
day one (pure reuse of `run_baseline` + `run_matrix`). For a Lean target the assembly scaffold
is a single theorem whose leaves are hypotheses:

```lean
-- sufficiency scaffold for cutting P into L₁…Lₙ. Leaves are HYPOTHESES; derive P from them.
-- GREEN + axioms ⊆ {propext, Classical.choice, Quot.sound} ⟹  L₁ ∧ … ∧ Lₙ ⟹ P.
theorem P_from_leaves (hL₁ : <L₁ prop>) … (hLₙ : <Lₙ prop>) : <P prop> := by
  <assembly using hL₁ … hLₙ>          -- e.g. the live run's `eLpNorm_integral_le` assembly
```

```python
# recurvelib/analysis/sufficiency.py  (NEW)
from recurvelib.core.baseline import run_baseline
from recurvelib.core.conformance import run_matrix

def sufficiency_ok(cut, ctx) -> bool:
    """True iff the cut's assembly claim is kernel-clean GREEN — i.e. the leaves imply P.
    Pure reuse: emit the assembly scaffold + its RED-first probe/trap, baseline it, gate it."""
    write_assembly_scaffold(cut)                       # the Lean theorem above + its .check + sorried trap
    _outcomes, ok = run_baseline(ctx.config, cut.suite, ctx.today)   # arms drafts RED-first
    if not ok:
        return False
    report = run_matrix(ctx.config, only=[cut.assembly_id])          # the arbiter
    return report.verdict_of(cut.assembly_id) == "GREEN"
```

Two guards make a wrong cut harmless: a bad **cut** fails here (assembly RED); a bad **leaf** is
caught RED-first at arming — `run_baseline` promotes a GREEN leaf to `closed` **only after** its
trap was seen RED (see `core/baseline.py` docstring), so a vacuous leaf cannot be born GREEN.

## 1.3 The one required schema change: a parent→child edge on `Gap`

`core/model.py:Gap` today has `covers: tuple[str, ...]` — but that is *GAPS.md prose anchors*,
**not** a claim-to-claim edge. Root-completion (§2.5) needs the decomposition DAG to be
first-class. Add it:

```python
# recurvelib/core/model.py — in the Gap dataclass, beside `covers`:
covers_claim: tuple[str, ...] = ()   # parent claim ids this leaf helps discharge (the decomposition edge)

# in Gap.parse (~line 171, mirroring the existing `covers` parse):
cc_raw = raw.get("covers_claim") or []
if not isinstance(cc_raw, list):
    raise GapParseError(f"{source_file}: gap {gid!r} 'covers_claim' must be a list of claim ids")
covers_claim = tuple(str(c) for c in cc_raw)   # …and pass covers_claim=covers_claim to Gap(...)
```

In `gaps.draft.yaml`, a decomposition then looks like (leaves point up; the assembly is a leaf too):

```yaml
- id: SUB-PROD-YOUNG          # a leaf
  covers_claim: [SUB-PROD]    # discharges part of its parent
  probe: probes/sub-prod-young.sh
- id: SUB-PROD-ASSEMBLY       # the sufficiency certificate (§1.2)
  covers_claim: [SUB-PROD]
  probe: probes/sub-prod-assembly.sh
```

## 1.4 The proposer: extend `analysis/claimify.py`

`claimify.py` already turns a spec into falsifiable drafts (observable + adversarial-twin +
ambiguity→ADJUDICATE). The decompose move reuses that machinery with two changes: the input is an
**open ledger node** (not a PRD), and it must additionally emit the **assembly** draft (§1.2) and
set `covers_claim` on every draft. Emitting the leaf drafts is exactly the shape `run_baseline`
already consumes, so no new arming path is needed.

**Golden test (Phase 1 acceptance).** Pointed at `‖fg‖_Hˢ ≤ C‖f‖_Hˢ‖g‖_Hˢ`, the proposer emits a
cut (Peetre split + Young inequality + L¹-factor bound + integrability leaf) whose **assembly
compiles kernel-clean**, and whose leaves match — up to renaming — the ones a human authored in
`navier_stokes/.recurve/claims/substrate/`.

---

# Part 2 — Build the cohesive loop with a controller

The mistake to avoid is treating "recurse" and "discover" as separate tools a controller
*switches between*. They are **moves** in one traversal.

## 2.1 The unifying object: `loop/solver.py`

Every open node is an **obligation**; the recursion picks the move its shape calls for:

```python
# recurvelib/loop/solver.py  (NEW) — one recursive step on an obligation.
from enum import Enum
class Move(Enum):
    REFUTE = "refute"; CLOSE = "close"; DECOMPOSE = "decompose"
    DISCOVER = "discover"; RESTATE = "restate"

def solve(node, ctx):   # ctx carries config, budget, ns_repo, today, ledger
    if try_refute(node, ctx):                 # cheap, first (falsify before investing)
        return restate_or_abandon(node, ctx)  # → RESTATE move (e.g. the SUB-HEAT-SG → -FWD fix)
    if try_close(node, ctx):                  # direct proof attempt — one cycle of the existing loop
        return CLOSED
    if goal_shape(node) == "∃" and has_proxy(node.domain):
        return discover(node, ctx)            # DISCOVER = fansearch (§2.4)
    cut = propose_cut(node, ctx)              # claimify-style proposer (§1.4)
    if cut and sufficiency_ok(cut, ctx):      # DECOMPOSE, gated by §1.2
        arm_leaves(cut, ctx)                  # core.baseline.run_baseline
        for leaf in order_by_tractability(cut.leaves, ctx):   # §2.3
            solve(leaf, ctx)                  # recurse
        return assemble(node, cut, ctx)       # discharge P from now-GREEN leaves; propagate up (§2.5)
    return frontier(node, ctx)                # no move applies → surface the precise open statement
```

"Recursive driver" and "fansearch" were never two systems — they are the `DECOMPOSE` and
`DISCOVER` arms of this one function.

## 2.2 How the controller knows which move: `analysis/shape.py`

Three cheap signals, in order — mostly mechanical, not taste:

1. **Node logical shape.** `∃ x, P x` (find a witness) → `DISCOVER`; `∀ …`/implication (prove) →
   `CLOSE`/`DECOMPOSE`. For a Lean claim the goal *type* is its shape:

   ```python
   # recurvelib/analysis/shape.py  (NEW)
   def goal_shape(node) -> str:
       # elaborate the claim's statement pin and inspect its head, or (cheap) regex the target
       # proposition in the claim's smallest_fix / check file. `∃`/`Exists` → "∃"; else "∀".
       return "∃" if _is_existential(node.statement) else "∀"
   ```
2. **Signal availability.** `DISCOVER` needs `node.domain in PROXY_ADAPTERS`; `CLOSE`/`DECOMPOSE`
   need library support to scout. Absent ⟹ that move is off the table.
3. **Cheap-first, then prune.** The order in `solve` (refute→close→discover/decompose) is the
   cost order; the gate, the tractability estimate, and the trap prune what doesn't stick. **The
   controller tries and backs off — it doesn't have to know in advance.** A wrong pick
   self-corrects: the dead route *parks* (`recurve park`), it takes the sibling.

Only when several moves are valid, none clearly more tractable, *and* the node is genuinely
unknown does it need taste — that is the **frontier**, surfaced (§2.3), never automated.

## 2.3 Navigation and halting — reuse the stopping controller, add tractability

- **Steer by tractability.** Extend the existing sort key in `analysis/triage.py:triage`
  (currently `(severity_rank, class_tiebreak, id)`) with a tractability term:

  ```python
  # analysis/triage.py — richer key; tractability(g): +library-support, +statement-elaborates, −subtree-depth
  key=lambda g: (rank.get(g.severity, 9), _CLS_TIEBREAK[g.gap_class], -tractability(g, config), g.id)
  ```
  On any **forced** tree (all of $T_0/T_1$) this alone drives the loop — no fitness oracle,
  because the gate + scouting + parking *are* the direction signal.
- **Halt / revert / pivot: reuse `loop/controller.py:decide`.** Each cycle, build `Progress`
  from the gate via `loop/runtime.py:sense_measured(gate_counts, surface, …)` and ask
  `decide(history)` for `CONTINUE / STOP-SUCCESS / STOP-REVERT / PIVOT`. **The frontier is
  already a field** — `Progress.uncovered`; a surfaced frontier node increments it. Do **not**
  re-implement halt logic; wire into this (`stopping-controller.md`).
- **Surface the frontier.** `frontier(node, ctx)` writes the node's *precise open statement*
  (its exact Lean goal) as a parked claim + a line for the human/campaign layer. That statement
  is the socket a human idea or a fitness search plugs into.
- **Budget.** The driver stops when the spend budget is exhausted regardless of `Verdict`
  (carry it in `ctx.budget`, checked before each `solve`), so a misdirected leg costs at most one
  budget — the one failure with no oracle.

## 2.4 The `DISCOVER` move *is* fansearch — call it, don't rebuild it

At an `∃`-node with a registered proxy, delegate to the existing campaign loop:

```python
# inside solve(), the DISCOVER branch:
from recurvelib.fansearch.campaign import run_campaign
from recurvelib.fansearch.promote import promote_candidate

def discover(node, ctx):
    summary = run_campaign(ctx.config, node.domain, ctx.ns_repo,
                           budget_seconds=ctx.budget.remaining(), seed0=node.seed)
    if summary.gate_confirmed:                       # a candidate elaborated kernel-clean at the real gate
        promote_candidate(ctx.config, node.domain, ctx.ns_repo,
                          round=summary.best_round, claim_id=node.leaf_id)   # → a CLOSED leaf
        return CLOSED
    return frontier(node, ctx)                       # search dry → surface it
```

`run_campaign` already does propose (`propose_candidate`) → proxy score (`proxy.score`) →
gate-confirm (`verify_compiled_claim`, read-only against the real repo) → archive. Its
gate-confirmed object becomes a **proved leaf**; `solve` then assembles upward. The seam between
`DECOMPOSE` and `DISCOVER` is exactly the seam in §2.2 — forced route vs. find-an-object — which
is why they compose instead of stacking.

## 2.5 Root-completion — propagate up the parent edge

```python
# when a leaf goes CLOSED, discharge any parent whose children are all closed; recurse; root ⟹ done.
def close_upward(ledger, closed_id, ctx):
    for parent in ledger.parents_of(closed_id):                 # via the new covers_claim edge (§1.3)
        if all(ledger[c].status == Status.CLOSED for c in ledger.children_of(parent)):
            # arm+prove the parent's assembly from the now-GREEN leaves, then recurse
            if assemble_and_gate(parent, ctx):
                close_upward(ledger, parent, ctx)
# solve() halts when the ROOT id is CLOSED — not when a flat ledger happens to empty.
```

## 2.6 Why it flows organically — moves nest and interleave

Every child is just another obligation with its own shape, so moves compose freely. The blowup
goal `∃ datum → finite-time singularity` is `∃` → **discover** the profile (proxy / numerics via
`run_campaign`). The discovered profile spawns a `∀` obligation — *prove it is a genuine
singularity* (a CAP) → **decompose/close**. One goal flows **discover → prove** in a single
`solve` recursion; nobody chose a tool, the terrain did. That is the cohesive flow: a
heterogeneous tree (`∀` and `∃` nodes mixed) expanded by one function keyed on shape.

## 2.7 Why unattended recursion can't corrupt anything

Three guards, none trusting the controller or its proposer: a bad **cut** fails
`sufficiency_ok` (§1.2); a bad **leaf** is caught RED-first by `run_baseline` (§1.2); a
misdirected-but-valid run wastes at most **one budget** (§2.3). The kernel (`run_matrix`) remains
the sole certifier.

---

# Build phases and acceptance

- **Phase 1 — `analysis/sufficiency.py` + the `covers_claim` edge.** Given a *hand-written* cut,
  arm its assembly RED-first and report GREEN/RED (pure `run_baseline` + `run_matrix` reuse).
  *Accept:* re-cut the Hˢ crux in `navier_stokes` substrate; the assembly compiles kernel-clean.
- **Phase 2 — `loop/solver.py` (close + decompose) + root-completion.** Recurse on a too-big
  obligation via `propose_cut` + `sufficiency_ok`, arm leaves, order by the extended
  `triage` key, and `close_upward` to a halt-on-root. *Accept:* close the Hˢ crux end-to-end with
  **zero human turns between leaves**, driven only by `recurve`-level calls.
- **Phase 3 — the full controller (`shape.py`, discover, refute, restate, frontier, budget).**
  Add the `∃`-shape → `run_campaign` discover branch, falsification-first + restate, frontier
  surfacing (parked precise statements), and wire halt into `loop/controller.py:decide` + the
  budget. *Accept:* on a goal like blowup, one `solve` recursion flows `∃`-discover → `∀`-prove,
  halts *honestly* at any genuine frontier with the exact open statement, spends within budget
  rather than spinning, and leaves a reconstructable record (fansearch archive + parked claims +
  cycle records in `io/records.py`).

# Non-goals and risks

- **It does not conquer $T_3$.** On genuinely unknown layers it *reaches and surfaces* the
  frontier; it does not invent the apex idea. Claiming otherwise is the inflation to avoid.
- **It adds no new arbiter.** Sufficiency is checked by the existing gate; provability and taste
  stay adjudicated by closing/failing and by the human. `run_matrix` is still the only certifier.
- **Spinning, not misdirection, is the risk** — bounded by budget + `decide`'s no-progress
  logic; misdirection is cheap because dead routes park.
- **Sufficiency-but-false leaves.** A cut can compile while a leaf is itself false. `frontier`
  should *flag* any leaf with no scouted library support so the human sees it before spend; the
  loop adjudicates the rest by failing to close it.
- **Reuse, don't fork.** The stop/spend brain (`loop/controller.py`, `stopping-controller.md`),
  the arming path (`core/baseline.py`), and the discover loop (`fansearch/campaign.py`) already
  exist. New code is `sufficiency.py`, `solver.py`, `shape.py`, the `covers_claim` edge, and the
  `triage`/`claimify` extensions — nothing more.
