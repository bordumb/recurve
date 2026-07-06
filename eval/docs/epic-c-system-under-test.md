# Epic C — Decouple the system under test (recurve)

**Leverage:** medium-high (removes real duplication now; enables SUT swaps later).
**Depends on:** nothing. Can proceed in parallel with A/B/D/F.

> **Prelaunch call:** do **C1–C3** (collapse the six `recurve` gate copies into one
> adapter — pure debt, obviously correct). **Defer C4** (the `SystemUnderTest`
> protocol/registry): there is exactly one SUT today (recurve), and a
> one-implementation port is just indirection. The `sut/recurve.py` adapter you
> build in C1–C3 *is* the seam; add the registry the day a second SUT is real. See
> the [README prelaunch lens](README.md#prelaunch--solo-lens-read-this-before-you-touch-anything).

---

## So what? (plain English)

`eval/` exists to measure **recurve**, so it legitimately needs to run recurve's
gate, init a recurve workspace, and invoke `recurve decide`. That coupling is
*fine in principle*. What's **not** fine is that the single command `recurve
matrix --gate` is hand-written as a raw subprocess in **six different files**.
Change how the gate is invoked — a new flag, a timeout, a JSON output mode, a
different recurve version — and you must find and edit all six, or the harness
silently measures inconsistently across arms.

Two separable goals:
1. **Now (pure debt):** collapse the six copies into one adapter. Cheap, obviously correct.
2. **Later (optional):** put that adapter behind a `SystemUnderTest` port so the
   harness could measure a *newer recurve*, a *competitor*, or a *customer's own
   framework* without kernel surgery. Only worth it if that's on the roadmap.

## Current state (evidence)

**Six sites shell out to the SUT**, most re-implementing the identical gate call:

```
evallib/done_signal.py:30      subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace ...)
evallib/orchestrate.py:58      subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace ...)
evallib/swebench_pipeline.py:238 subprocess.run(["recurve","matrix","--gate"], cwd=.../"testbed" ...)
evallib/adapters/claude.py:116 subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace ...)
evallib/swebench_pipeline.py:155 subprocess.run(["recurve","decide", ...])          # recurve decide
evallib/audit.py:78            subprocess.run(["recurve","drill","--fuzz","--iso","--diff"])
```

All four `matrix --gate` copies implement the *same* mapping
`{0: "green", 1: "red"}.get(rc, "broken")` — four chances to drift. (Epic A's A4
removes one of them by deleting the fork; this epic removes the rest.)

**Deeper SUT knowledge is spread around too** (this is the "abstract it" half):
- `classify.py:32-38` reads recurve's on-disk `probes/*.sh` + `.trap` layout to
  decide `has_wellformed_claim` — it knows the SUT's *file format*.
- `swebench_pipeline.py:125-139` string-patches the SUT's `.recurve/recurve.toml`
  `[gate] governor=` table.
- `swebench_pipeline.py:153` sets `RECURVE_GOVERNOR_CMD` / `RECURVE_ACTOR_MODEL`.
- `materialize.py:62-70` runs `recurve init`.
- `arms.py:32-34` imports `recurvelib.adapters.*` directly (the one legitimate,
  intended cross-import — leave it).

## Target design

### Now: one gate/SUT adapter module

```python
# sut/recurve.py  (target — the ONLY place that names the `recurve` binary)
GATE_MAP = {0: "green", 1: "red"}
def gate_verdict(workspace: Path) -> str:
    r = subprocess.run(["recurve", "matrix", "--gate"], cwd=workspace, capture_output=True, text=True)
    return GATE_MAP.get(r.returncode, "broken")
def gate_green(workspace) -> bool: return gate_verdict(workspace) == "green"
def init(workspace): ...            # `recurve init`
def decide(testbed, **kw): ...      # `recurve decide` (from swebench_pipeline.run_recurve_decide)
def has_wellformed_claim(ws): ...   # moved from classify.py — SUT file-format knowledge lives here
```

Every one of the six sites imports and calls this. The kernel modules
(`orchestrate`, `done_signal`, `runner`) no longer contain the string `"recurve"`.

### Later (optional): a `SystemUnderTest` port

If measuring a non-recurve SUT is ever real, the adapter above already *is* the
port's `recurve` implementation. Add a protocol + registry mirroring the arm
ports:

```python
class SystemUnderTest(Protocol):
    def init(self, workspace): ...
    def gate_verdict(self, workspace) -> str: ...
    def decide(self, workspace, **kw) -> str: ...
    def has_wellformed_claim(self, workspace) -> bool: ...
SUTS = {"recurve": RecurveSUT()}          # name from the manifest, default "recurve"
```

The arm's `workspace="recurve_init"` / `done_signal="gate"` values stay; they just
resolve their SUT operations through the port instead of hardcoding `recurve`.
**Do not build this speculatively** — do the "Now" collapse first; add the port
only when a second SUT exists on paper.

## Tasks

- [ ] **C1 — Create `sut/recurve.py` with `gate_verdict`/`gate_green`.** Replace
  the four `matrix --gate` subprocess copies (`done_signal.py:30`,
  `orchestrate.py:58`, `adapters/claude.py:116`, and — after Epic A/A4 —
  `swebench` grading) with imports of it. *Acceptance:* `grep -rn 'matrix", "--gate'
  evallib/` returns exactly one hit (in `sut/recurve.py`); gate behavior unchanged.

- [ ] **C2 — Move `recurve init` and `recurve decide` into the adapter.**
  `materialize.recurve_init_workspace` and
  `swebench_pipeline.run_recurve_decide` call `sut/recurve.py`. *Acceptance:* the
  only file naming the `recurve` binary is `sut/recurve.py`.

- [ ] **C3 — Move SUT file-format knowledge in.** Relocate
  `classify.has_wellformed_claim` (the `probes/*.sh` + `.trap` scan) and the
  `.recurve/recurve.toml` governor patch into `sut/recurve.py`. `classify.py`
  keeps only benchmark-agnostic outcome classification. *Acceptance:* `classify.py`
  no longer references `probes`, `.trap`, or `.recurve`.

- [ ] **C4 (optional, roadmap-gated) — Introduce the `SystemUnderTest` protocol +
  registry.** Only if a second SUT is planned. *Acceptance:* `arms`/`orchestrate`
  resolve SUT ops via `SUTS[manifest.get("sut","recurve")]`; `recurve` remains the
  default and the sole implementation.

## Risks & constraints

- **`cwd` differs by benchmark.** BCB gates in `workspace`; SWE gates in
  `workspace/"testbed"` (`swebench_pipeline.py:238`). The adapter takes the gate
  directory as its argument — don't hardcode one.
- **Don't over-abstract.** C1–C3 are unambiguous wins. C4 is only worth its weight
  if there's a real second SUT; a one-implementation port is just indirection.
  This is a judgment call for the tech lead, flagged deliberately.
- **`arms.py`'s import of `recurvelib.adapters` is intended** (adversary/governor
  live in the engine and are resolved through its own registry —
  `ablation-infra.md` AI5). Leave it; it is not part of this cleanup.
