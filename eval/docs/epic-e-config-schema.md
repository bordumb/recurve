# Epic E — A manifest that declares, not assumes

**Leverage:** medium-high (this is the "are configs dynamic enough?" answer).
**Depends on:** Epic A for the `benchmark` dispatch part; the rest is independent.

---

## So what? (plain English)

A good experiment manifest should be a *complete, honest declaration* of the
experiment: read it and you know exactly what will run. This one has four leaks
where the manifest either says something the code ignores, or omits something the
code assumes:

1. It **names a benchmark that the code ignores** (`benchmark = "bigcodebench-hard"`
   is written but never dispatched on).
2. **Arms aren't in the manifest at all** — they're a Python dict, so a new
   experimental condition is a code change, not a config change.
3. **Dataset pins are copy-pasted** into every experiment file; change a dataset
   and you edit N files, with no lock to catch a mismatch.
4. **The budget field has two different units** across files with no way to tell
   which is meant — a silent correctness hazard for a spend-gated system.

None of these is catastrophic alone; together they mean the manifest can't be
trusted as the single source of truth it's supposed to be
(`eval/README.md:8-12`: "The manifest is human intent; the lock is machine-resolved
truth").

## Current state (evidence)

**1. `benchmark` is written and ignored** — see [Epic B](epic-b-unified-cli.md);
`_resolve_tasks` (`cli.py:22-30`) hardcodes `fetch_bigcodebench_hard` regardless.

**2. Arms live in Python, not config:**

```python
# evallib/arms.py:77-109 — the only place an arm can be defined
_ARMS = {"A0": ArmSpec(workspace="bare", done_signal="self_report", ...),
         "A3": _A3, "A4": ..., "A7": ..., "A10": ...}
```

The manifest can only *name* arms (`arms = ["A0","A3"]`); it can't *define* one. A
new port combination is a code edit + a release.

**3. Dataset pins duplicated across experiments** — the identical block appears in
`experiments/o6-smoke.toml:16-22`, `poc-bcb-hard.toml:11-25`, and (a different
dataset, same pattern) `sw6-smoke.toml:18-30`:

```toml
local = "datasets/bigcodebench-hard@298d2cc...jsonl"
revision = "298d2cc7b96612e15e47313c3603ee124cee0c1f"
hash = "e2f21cd5...883fd"
count = 148
```

Three experiments, one dataset, three hand-copied pins. Nothing enforces they
agree.

**4. Budget-unit drift** — same key, two units, no discriminator:

```toml
# experiments/poc-bcb-hard.toml:8      budgets = [0.50]     # DOLLARS  (comment says --max-budget-usd)
# runs/o6/manifest.toml:12             budgets = [60000]    # TOKENS   (a frozen older run)
```

`cli.py:183` casts `int(budgets[0])`; `adapters/claude.py:87` reads it as dollars.
A 60000 there means "$60,000 per cell" to today's code. The units diverged and the
schema can't tell.

## Target design

Make the manifest a validated, versioned declaration; lift the duplicated pins
into a shared registry; make arms declarable in config; fix the budget unit.

- **Versioned + validated.** Add `schema_version` and a JSON-Schema (or a
  `validate_manifest(dict)` in `plan.py`) run at `eval plan`, so a typo or a
  missing required key fails loud *before* a run, not mysteriously during one.
- **Dataset registry.** `datasets/registry.toml` maps a dataset name → its pin
  (`local`/`revision`/`hash`/`count`). Experiments reference it by name:
  `[tasks] benchmark = "bigcodebench-hard"` and the pin is looked up, not copied.
  One source of truth; a drifted copy becomes impossible.
- **Declarable arms.** Allow an `[arms.<name>]` table in the manifest carrying the
  six port values, resolved through the *same* registry validation `resolved_gate_config`
  already applies (`plan.py:44-76`). The Python `_ARMS` stays as the built-in
  library of named presets; the manifest can add ad-hoc ones without a release.
- **One budget unit.** Standardize on dollars (the spend gate is dollar-based) and
  add an explicit `budget_unit = "usd"` field; reject a manifest whose numbers look
  like tokens under a `usd` unit (a >100 sanity bound), or support both units
  explicitly with the field as the discriminator.

## Tasks

- [ ] **E1 — `validate_manifest` at plan time.** A schema (required keys, types,
  enums for `mode`/`verdict`) checked in `cmd_plan` before any resolution.
  *Acceptance:* a manifest missing `[tasks].hash` or naming an unknown `benchmark`
  fails with a precise message; valid manifests unchanged.

- [ ] **E2 — Dataset registry.** Add `datasets/registry.toml`; `load_tasks`
  (Epic A seam) looks up the pin by benchmark/dataset name. Migrate the three
  experiment files to reference it. *Acceptance:* the BCB pin exists in exactly one
  place; editing it there flows to all experiments; a stale inline pin is rejected.

- [ ] **E3 — Add `budget_unit` + reconcile the drift.** Introduce the field
  (default `"usd"`); update `cli.py:183` / `claude.py:87` to honor it; add a range
  sanity check. Re-annotate `runs/o6/manifest.toml` as historical/token-unit so its
  replay stays correct. *Acceptance:* no manifest can be ambiguous about whether
  `budgets = [60000]` means dollars or tokens.

- [ ] **E4 — Manifest-declarable arms.** Parse `[arms.<name>]` tables into
  `ArmSpec`s through the existing registry validation. *Acceptance:* an experiment
  can add a new port combination without editing `arms.py`; a typo'd port value in
  a declared arm fails the plan (not the run), same as today's built-ins.

- [ ] **E5 — Round-trip test.** A manifest → plan → frozen `manifest.toml` →
  replan produces identical matrices, proving the schema is stable and the freeze
  is faithful. *Acceptance:* deterministic re-plan.

## Risks & constraints

- **The freeze-at-plan contract is load-bearing.** `cmd_plan` copies the manifest
  into the run dir so old runs stay legible (`cli.py:40`). Registry indirection
  must be *resolved and frozen* into the run (write the resolved pin into the run's
  `manifest.toml`/`matrix.jsonl`), not left as a dangling reference to a registry
  that may change later. Resolve-then-freeze, never freeze-a-pointer.
- **Backward compatibility — void (prelaunch).** Per the [README prelaunch
  lens](README.md#prelaunch--solo-lens-read-this-before-you-touch-anything), there's
  nothing to preserve: one real run on disk. Don't build legacy defaults or
  deprecation shims — just migrate/delete `runs/o6/` and require the new fields
  outright. **Skip E4 (declarable arms)** until a second experiment actually needs
  an ad-hoc arm; `_ARMS` in Python is fine and type-safe for now.
- **Don't turn the manifest into a program.** Declarable arms are port *values*,
  not arbitrary logic. Keep the "an arm is a tuple of port selections, nothing
  else" invariant (`eval-arm-kernel.md`); config that can express behavior beyond
  the ports would reintroduce the special-casing the kernel removed.
