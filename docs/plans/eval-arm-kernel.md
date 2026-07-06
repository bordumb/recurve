# PRD — the arm kernel: ports for what varies between arms

> Scope: `eval/evallib`'s arm composition, plus one new `recurvelib.adapters`
> port. Problem this fixes: `arms.py`'s `_ARMS` dict has exactly one shape
> (`recurve: bool`, `config: dict`) and it only fits two of the six things
> an arm can vary. Adding A2/A4/A5/A6 by stuffing more ad-hoc keys into that
> dict is how you get the "messy dump of coupled code" this doc exists to
> prevent. The fix is the same one `ablation-infra.md` already applied to
> Adversary/Governor — a kernel that composes named ports, never a growing
> pile of special cases.

## 1 · What actually varies between arms (the six axes)

| Axis | Question it answers | Current state |
|---|---|---|
| **Workspace** | is the cell `recurve init`-ed at all | in `arms.py`, as a bare `bool` |
| **Done signal** | what decides the cell is over, and how | **doesn't exist as a concept** — implicit in whether a gate is consulted |
| **Boundary** | can the actor touch claims/probes/traps | no config exists; presumably always-on |
| **Audit** | does a post-hoc hardening pass run and get recorded | **doesn't exist** |
| **Adversary** | per-claim decorrelation | built (`recurvelib.adapters.adversary`) |
| **Governor** | run-level decorrelation | built (`recurvelib.adapters.governor`) |

Six axes, six ports. An arm is a **tuple of port selections** — nothing
else. A0's and A3's current behavior must come out byte-identical after
this refactor; that's the regression fixture (K1).

## 2 · The kernel

The cell-runner becomes a fixed pipeline with slots, each slot filled by a
port lookup — it never branches on which arm is running:

```
workspace   = WorkspacePort[arm.workspace](task)              # bare | recurve_init
              apply BoundaryPort[arm.boundary] to workspace     # enforced | open
agent_result = run_agent(workspace, model, budget)              # unchanged
declared     = DoneSignalPort[arm.done_signal](workspace, agent_result)  # gate | self_report | external_ci
if arm.audit != "none":
    audit_result = AuditPort[arm.audit](workspace)               # none | drill_hardened
oracle_verdict = quarantine(workspace)                          # unchanged
row = merge(agent_result, declared, audit_result, oracle_verdict, provenance)
```

Adding an arm is a new `ArmSpec` tuple. Adding a *new port value* (e.g. a
future `done_signal="external_ci"` adapter for SWE-bench) is one adapter
file plus one registry line. **Neither ever touches this pipeline** — same
property `ablation-infra.md`'s AI2 proved for Adversary/Governor, applied
here.

## 3 · Where each port lives, and why

| Port | Values | Lives in | Why there |
|---|---|---|---|
| `WorkspacePort` | `bare`, `recurve_init` | `eval/evallib` | pure materialization, eval-only concern |
| `DoneSignalPort` | `gate`, `self_report`, `external_ci` | `eval/evallib` | exists to *simulate absence* of recurve's discipline for measurement — no real `/recurve-work` user should ever want `self_report` |
| `BoundaryPort` | `enforced`, `open` | `recurvelib.adapters` | the boundary itself is core engine safety machinery; `open` is a real (if dangerous) engine capability, not an eval fiction |
| `AuditPort` | `none`, `drill_hardened` | `eval/evallib` | wraps the existing `drill` CLI as a post-hoc measurement, not an engine concept |
| `AdversaryPort`, `GovernorPort` | (existing) | `recurvelib.adapters` | already built; reused unchanged |

The test that decides placement, same one `ablation-infra.md` used: *would
a real recurve user, outside any eval, ever want this?* Yes → `recurvelib`.
Only meaningful as a counterfactual for measurement → `eval/evallib`.

## 4 · The CLI contract, per port

Ports that are genuinely decisions get a shell-command escape hatch, so
plugging in a new benchmark's grading convention is a config string, not
new Python — the same pattern `AGENT_CMD`/`Gap.reference` already set:

- **`DoneSignalPort["external_ci"]`** — any command; exit 0 = done, exit 1
  = not yet. This is *the* port that unlocks A1 for SWE-bench Verified
  later: "the repo's own `pytest`" becomes a config string, zero new code.
- **`AuditPort["drill_hardened"]`** — literally invokes the existing
  `drill --fuzz --iso --diff` CLI against the cell's workspace; already a
  CLI contract, just newly wrapped as a port.
- **`BoundaryPort["open"]`** — a config flag inside `recurvelib`, not a
  subprocess (there's no external tool to plug in here — see requirement
  K3 for why it still needs to be hard to reach by accident).
- **`WorkspacePort`** — Python-only. Materialization is deterministic setup,
  not a decision; no reason an external tool substitutes it.

## 5 · Requirements

### K1 — `ArmSpec` replaces the flat dict; A0/A3/A7–A10 unchanged

**Assertion.** Every arm is `ArmSpec(workspace, done_signal, boundary,
audit, adversary, governor)`. A0 = `(bare, self_report, enforced, none,
off, off)`. A3 = `(recurve_init, gate, enforced, none, off, off)`. A7–A10
extend A3 by `adversary`/`governor` only, unchanged from today.

**Counterexamples (traps).** A0/A3/A7–A10 cells run through the new
`ArmSpec` shape must produce byte-identical results to the pre-refactor
`_ARMS` dict on the same fixture (regression fixture — this PRD is not
allowed to change existing behavior). Adding a 7th axis later must not
require editing any existing `ArmSpec` value (new field, defaulted).

**Bounds.** Pure refactor of `arms.py`; no behavior change for anything
already running.

### K2 — Two new insights, not two new special cases: A0 and A6 share a port

**Assertion.** A0 (`bare`) and A6 (`controller off`) are the *same*
`done_signal="self_report"` — they differ only in `workspace`. Building
`DoneSignalPort["self_report"]` once yields both arms; A6 does not need
its own bespoke "ignore the gate" logic.

**Counterexamples (traps).** A cell with `workspace="recurve_init"` and
`done_signal="self_report"` (A6) must show a real recurve ledger present
in the workspace, *unconsulted* for the declared-done decision — a fixture
proving the gate's own verdict (even if red) has zero effect on the
recorded outcome under this port.

**Bounds.** This is the reason to build the port lookup, not a shortcut
around it — the insight only pays off if A0 and A6 actually share code.

### K3 — `BoundaryPort["open"]` is real, and hard to reach by accident

**Assertion.** A config-driven bypass of `within_boundary()` exists in
`recurvelib`, off by default, reachable only by an explicit, unambiguous
key (not a value any other config path could produce by coincidence).

**Counterexamples (traps).** A fixture sweeping realistic-looking
`recurve.toml` permutations (typos, partial configs, other arms' configs)
must show none of them accidentally resolve to `open`. A run with
`boundary="open"` must record that fact loudly in the row's provenance —
never silently.

**Bounds.** This is the one port this PRD treats as inherently dangerous;
scope the implementation to the minimum needed for A5, resist generalizing
it further.

### K4 — `DoneSignalPort["external_ci"]` is genuinely CLI-expressed

**Assertion.** Grading via an external command requires zero new Python to
add — a config string naming a shell command is sufficient.

**Counterexamples (traps).** A trivial fixture (`test -f solution.py`) as
the configured command proves this end-to-end with no new adapter code
for that specific check.

**Bounds.** This closes A1's *mechanism* gap; A1 is still blocked on the
separate design question (§6) of what "the repo's own tests" means for a
benchmark with no repo.

### K5 — `AuditPort` can only add columns, never change the outcome

**Assertion.** `drill_hardened`'s result is additive to a row; it cannot
touch `declared_done` or `oracle_verdict`.

**Counterexamples (traps).** An audit adapter attempting to set either
field must fail structurally (the function's return type doesn't carry
those fields at all — not a runtime check, a type-level impossibility).

**Bounds.** Keeps A4 answering "how much would harder auditing have
caught" without becoming a second gate.

## 6 · What this doesn't fix

A1 needs a design answer, not just `DoneSignalPort["external_ci"]`: what
does "the repo's own CI" mean for a benchmark task with no repo? That's a
`eval-full.md` E2/SWE-bench Verified question — real repos have real CI to
point `external_ci` at. Building K4 now means A1 is a config change
*whenever* E2 lands, not a blocked engineering task later.

## 7 · Sequencing

K1 (ArmSpec + regression fixture) → K2 (the shared `self_report` port,
unlocking A6 and revealing A0 as its sibling) → K3 (`BoundaryPort`,
unlocking A5) → K4 (`external_ci`, mechanism ready for A1 whenever E2
exists) → K5 (`AuditPort`, unlocking A4). Each step adds one arm; none
touches the kernel pipeline in §2.
