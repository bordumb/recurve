# Multi-repo work: completing the `[sculpts.*]` production path

> Status: feature-completion. The secondary-tree **model** (`SculptConfig`) and the **federated
> gate** (`matrix --gate` AND-s each sculpt's own gate into the verdict, guarded by the self-hosted
> trap `TK-16 · sculpt-fails-but-reports-green`) ship today. What is missing is the *production*
> half: the loop can **verify** a secondary tree but cannot **build, edit, or commit** one. This
> plan completes that. Origin-agnostic.

---

## The problem

A claim lives in the target tree, but its **honest fix does not**. The probe stays RED for a reason
no edit under `[target]` can resolve — the change it demands is a new symbol in an upstream library
the same author controls, or a rebuilt binary artifact the target only *consumes*.

The single-tree loop cannot close such a claim:

- `matrix --gate` can **run the upstream tree's gate** and refuse to go green until it passes — the
  verification half already works.
- But `recurve run` (the autonomous burndown loop) hands the agent exactly one tree
  (`TREE = cfg.tree`; see `run.py`). The agent has no surface for, and no mandate over, the second
  tree. It cannot add the upstream symbol, cannot rebuild the artifact, cannot commit to the
  upstream branch. So the loop spins on a RED claim it structurally cannot fix.

The result is a hand-off: a human builds the upstream change out-of-band, then the loop resumes and
finally sees the target probe go green. The loop verified the seam; it did not *drive* it. Making the
loop drive it is this plan.

---

## What ships today (the verify half)

| Piece | Where | State |
|---|---|---|
| `[sculpts.<name>]` config: `tree`, `branch`, `rebuild`, `gate`, `forbidden_strings` | `config.py · SculptConfig` | complete; zero `[sculpts.*]` ⇒ byte-identical to single-tree |
| **Federated gate** — each sculpt's `gate` run in its own tree, AND-ed into `matrix --gate` | `cli.py` (`for sname, sc in cfg.sculpts.items(): …`) | complete |
| Guard: a failing sculpt gate must not report green | `claims/toolkit · TK-16` trap | complete |
| `init` scaffolds the `[sculpts.<name>]` template | `init.py` | complete |
| Model/status/triage carry the "sculpting" gap state | `model.py`, `status.py` | complete |

The **federated verdict is real**: `matrix --gate` is green only when the target's probes *and* every
sculpt's own gate pass. A verifier already cannot be lied to about a secondary tree.

---

## What's missing (the produce half)

**G1 — `rebuild` is never executed.** `SculptConfig.rebuild` is documented as "how fresh artifacts
reach this tree's checks," but nothing runs it. `freshness.py` only *prints* `rebuild` as a stale-hint
string. So the artifact a sculpt produces — the compiled library, the generated binding — is never
built by the loop; it is stale until a human rebuilds it by hand.

**G2 — the run loop is single-tree.** `run.py` materializes `RUN.md` with a single `TREE`. The agent
contract, the per-cycle commit, and the tree lock all bind that one tree. There is no
`SCULPT_<name>_TREE`, no per-sculpt rebuild/gate/branch in the agent's environment, and no instruction
that a fix may belong upstream. The autonomous loop therefore cannot originate a secondary-tree change.

**G3 — cross-tree freshness is not wired.** A sculpt's built artifact reaching the target's *consumed*
path (the copy the target's probes exercise) is exactly a `reads: content-hash` relationship — but
across two trees. Today `reads` rules resolve within one config root; nothing binds "the artifact
`rebuild` produced in tree A" to "the file tree B consumes."

**G4 — per-tree commit-to-branch (FR-C2) is not executed by the loop.** The model carries
`sculpt.branch`; the loop never lands a sculpt commit on it. A multi-tree cycle needs each tree's
change committed to its own branch, independently revertable.

**G5 — per-tree forbidden-vocabulary (FR-C4) is advisory.** Each sculpt carries its own
`forbidden_strings`; nothing greps the sculpt tree for them. A leak from one tree's vocabulary into
another is caught only by a hand-authored source-grep probe, per tree.

---

## Design

The federated gate already answers *"is every tree green?"* This plan answers *"can the loop make
every tree green?"* — by teaching one cycle to span trees, in a fixed, safe order.

### Order of operations, per cycle

```
1. sense        target probes + each sculpt's gate  →  the federated RED set
2. sculpt       the agent edits the target tree OR a sculpt tree
                (the claim's "smallest honest fix" decides which)
3. rebuild      for every DIRTY sculpt: run sc.rebuild  → produce its artifact  (G1)
4. freshness    the produced artifact must reach the target's consumed path     (G3)
5. gate         re-run the sculpt gate(s) AND the target probes → federated verdict
6. commit       land each tree's change on ITS branch (target + each sculpt.branch)  (G4)
```

Steps 1 and 5 exist. Steps 3, 4, and 6 are the new execution; step 2 is the new *surface* (G2).
With no `[sculpts.*]`, steps 3–6 have zero iterations over sculpts and the cycle is byte-identical to
today — the standing invariant for every sculpt feature.

### The run-loop surface (G2)

`build_run` / `RUN.md` gain, per configured sculpt, the tuple the agent needs to act on a second tree:

- `SCULPT_<name>_TREE` — the resolved path the agent may edit.
- `SCULPT_<name>_REBUILD` — the command that turns a source edit into the consumed artifact.
- `SCULPT_<name>_GATE` — the tree's own gate (already run federated; surfaced so the agent can
  self-check before yielding).
- `SCULPT_<name>_BRANCH` — where a sculpt commit lands.

The per-cycle contract states the rule plainly: **the smallest honest fix decides the tree.** If the
target probe can only pass once an upstream symbol exists, the fix is upstream — the agent edits the
sculpt, runs its rebuild, and the target probe is the acceptance test for the whole cross-tree change.
The separation-of-refereeing invariant is unchanged: the probe (in the target) still referees; the
agent still never grades itself.

### Rebuild + freshness (G1, G3)

- **Execute `rebuild`** for a sculpt whose tree is dirty since last build (or unconditionally with
  `--rebuild-sculpts`), before the gate. A non-zero rebuild is a cycle failure, surfaced like a broken
  probe — never a silent stale pass.
- **Cross-tree `reads`.** Extend a `reads: content-hash` rule to name a *sculpt* as its `source`:
  the target artifact the probe consumes must be byte-identical to what the sculpt's `rebuild`
  produced. This makes "did the rebuilt binary actually land?" a measured freshness check, not trust.
  A stale consumed artifact is RED with the exact `rebuild:` hint `freshness.py` already renders.

### Commit + leakcheck (G4, G5)

- **Per-tree commit.** Reuse the existing per-cycle commit machinery once per tree, each on its own
  `branch`, so a cross-tree cycle is still one-command-revertable *per tree*.
- **Per-tree leakcheck.** Promote FR-C4 from advisory to a built-in `leakcheck` that greps each tree
  (target + every sculpt) for *that tree's* `forbidden_strings`, attributing each hit to its tree.
  The model already separates the vocabularies; this runs them.

---

## Incremental delivery

recurve self-hosts this — each phase is a RED-first claim in `claims/toolkit` (or a new
`claims/sculpts` suite) with a trap, landed behind `matrix --gate`.

1. **Rebuild execution (G1).** Run `sc.rebuild` before the gate; a failing rebuild is a hard gate
   failure. Trap: `rebuild-fails-but-gate-green`.
2. **Cross-tree freshness (G3).** `reads: content-hash` with a sculpt `source`. Trap:
   `stale-consumed-artifact-reports-fresh`.
3. **Run-loop surface (G2).** `SCULPT_<name>_{TREE,REBUILD,GATE,BRANCH}` in `RUN.md`; the
   contract's "smallest honest fix decides the tree" rule. Trap (self_recursion suite):
   `loop-ignores-upstream-fix` — a claim whose only fix is upstream must not close from target edits.
4. **Per-tree commit (G4).** Land each tree's change on its branch. Trap:
   `sculpt-change-committed-to-wrong-tree`.
5. **Leakcheck (G5).** `recurve leakcheck` per tree. Trap: `foreign-vocabulary-leaks-unattributed`.

Phases 1–2 are independently useful even under a human-driven loop (they make a hand-rebuilt artifact
*measured* rather than trusted). Phases 3–5 are what let the autonomous loop originate the cross-tree
change.

---

## Non-goals

- **Not a monorepo.** Sculpts stay separate repos with separate history, branches, and vocabularies;
  the loop federates them, it does not merge them.
- **Not remote orchestration.** A sculpt tree is a local path resolved against the config root. Remote
  checkouts, submodules, and CI fan-out are the caller's concern, upstream of recurve.
- **No new refereeing authority.** The federated gate's verdict rule is unchanged: green iff every
  tree is green. This plan only lets the loop *reach* that state.

---

## Provenance

The driving case: a demo repo hosts claims that a code-correctness verdict is emitted as a signed,
re-verifiable, standards-shaped attestation and anchored in an append-only log. Two of those claims
were only closeable by first adding a new signer + a native binding to an upstream library the same
author controls, then rebuilding its compiled extension — work outside the demo repo's `[target]`
tree. The federated gate could *verify* the upstream once built, but the autonomous loop could not
*build* it, so the upstream change was made by hand and the loop resumed to confirm the target probes.
That hand-off is precisely the gap G1–G5 close. (Concretely: the `auths-curve` suite's DSSE-verdict
and tlog-inclusion claims, whose fixes lived in the `auths` SDK + its Python extension.)
