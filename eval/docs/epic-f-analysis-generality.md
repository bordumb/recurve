# Epic F — Analysis generality (un-bake the A0-vs-A3 pair)

**Leverage:** medium (small change; prevents silently-missing results).
**Depends on:** nothing. Parallelizable. Cheapest epic; good starter task.

---

## So what? (plain English)

The analysis step computes the headline result — how much the gate reduces
false "done" claims — by comparing two arms. But *which* two arms is **hardcoded
to A0 vs A3.** The moment you run the ablation ladder (A4–A10) or SWE-bench (which
uses A0 vs **A9**), the paired comparison and the statistical test either compare
the wrong pair or silently produce nothing. You get tables with no ΔFDR and no
McNemar and no error — the most important number just quietly isn't there. For a
system whose entire pitch is "measure honestly," an analysis that silently drops
the key comparison is a sharp edge.

## Current state (evidence)

**ΔFDR only exists when both A0 and A3 are present:**

```python
# evallib/analyze.py:69-71
if "A0" in arms and "A3" in arms:
    entry["delta_fdr"] = arms["A0"]["fdr"] - arms["A3"]["fdr"]     # ← A4–A10, A9 get nothing
```

**The paired significance test is A0-vs-A3 by literal:**

```python
# evallib/analyze.py:75-82
def mcnemar(rows, model):
    a0 = {... for r in rows if r["arm"] == "A0"}                    # ← literal "A0"
    a3 = {... for r in rows if r["arm"] == "A3"}                    # ← literal "A3"
```

So `sw6-smoke` (arms A0/A9) and any ablation run get a summary with the tables but
**no ΔFDR line and no McNemar** — and nothing flags that the comparison was
skipped.

**Note what's already done right:** `figure_specs` (`analyze.py:157-227`) *infers*
the baseline and gated arms from the data (an arm carrying `gate_outcome` is the
gated one) rather than hardcoding names — "nothing here is baked to a particular
arm name" (`analyze.py:152-154`). The fix is to bring `metrics`/`mcnemar` up to
that same standard.

## Target design

Declare the comparison(s) in the manifest, and support **N treatments against one
baseline** (the ablation ladder is exactly this shape). Fall back to the existing
role-inference when the manifest doesn't specify.

```toml
# manifest  (target)
[analysis]
baseline   = "A0"
treatments = ["A3"]              # or ["A3","A4","A7","A8","A9","A10"] for the ablation ladder
                                 # SWE: baseline="A0", treatments=["A9"]
```

```python
# analyze.py  (target)
def metrics(rows, baseline=None, treatments=None):
    base, treats = _resolve_comparison(rows, baseline, treatments)   # manifest, else infer via _roles
    for t in treats:
        entry[f"delta_fdr[{t}]"] = arms[base]["fdr"] - arms[t]["fdr"]
def mcnemar(rows, model, baseline, treatment):                       # parameterized pair
    ...
```

When `[analysis]` is absent, reuse `_roles` (the baseline = the arm with no
`gate_outcome`; the treatment = the gated arm). If more than one gated arm exists
and no manifest says which is the headline, emit **all** baseline-vs-treatment
comparisons rather than silently picking one.

## Tasks

- [ ] **F1 — Parameterize `metrics`/`mcnemar` on `(baseline, treatments)`.**
  Default to `_roles` inference (already exists). *Acceptance:* an A0/A9 run
  produces a ΔFDR and a McNemar for that pair; today it produces neither.

- [ ] **F2 — Support N treatments vs one baseline.** Emit a ΔFDR + paired test per
  treatment. *Acceptance:* an ablation run (A0 baseline; A3,A4,A7–A10 treatments)
  yields one comparison row per treatment in `summary.md`.

- [ ] **F3 — Read `[analysis]` from the frozen manifest.** `analyze_and_emit`
  (`analyze.py:129`) takes the run dir, loads `manifest.toml`, passes the declared
  comparison through. *Acceptance:* the manifest chooses the headline pair; absent
  it, all inferred pairs are emitted (never silently one).

- [ ] **F4 — Loud on an impossible comparison.** If a declared arm is absent from
  the results, the summary states it explicitly ("A3 requested but no A3 rows")
  instead of emitting a blank. *Acceptance:* a mis-declared comparison is visible,
  not silent.

## Risks & constraints

- **Preserve determinism.** `analyze.py` is a pure, order-invariant function of the
  rows (`analyze.py:1-8`). Keep it that way — sort treatments, no dict-order
  dependence, no wall-clock.
- **Don't break the honesty guards.** `spec_is_honest` / `_endpoint_honest`
  (`analyze.py:230-250`) enforce full-[0,1] axes and CI-bracketing. Any new
  multi-treatment figure must pass the same guards.
- **Semantics of `oracle_env_hash` differ by benchmark** (shared vs per-instance —
  Epic A). Analysis that groups or reports by oracle env must not assume one shared
  hash per run for SWE-bench.
