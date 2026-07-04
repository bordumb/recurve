# PRD — recurvelib reorganization and a Typer CLI, gated differentially against the pre-refactor engine

> Source: the engine has grown a monolith. `recurvelib/cli.py` is 1,586 lines —
> 31 `cmd_*` functions and ~35 subcommands dispatched by one hand-assembled
> argparse tree — more than four times the next-largest module. The goal is
> navigability for future contributors: split the CLI monolith into a package a
> reader can hold in their head, adopt Typer as the dispatcher, and regroup the
> remaining flat modules by concern — all with **zero change to what any command
> does**.
>
> This is surgery on the judge, so the safety case comes first and is measured,
> not assumed. The coverage facts: 146 probe files, of which 29 shell out to the
> real CLI, **105 reference `recurvelib` and 57 directly import flat module
> paths the regroup would move** — the probes are coupled to the internal
> layout, and this PRD accounts for that instead of wishing it away. Two
> instruments anchor equivalence: **R0**, a differential harness that
> cross-examines the working engine against a **pinned pre-refactor baseline**
> (built from a recorded git ref) on identical fixtures — outputs *and*
> resulting state — and **R1**, a golden characterization harness that outlives
> the migration as a permanent guardian.
>
> Decisions, revised from the first draft and owned by the maintainer:
> **split-then-swap replaces the one-move rewrite** (each phase lands separately
> under a green gate, halving the blast radius per step); equivalence is
> **differential against the pinned baseline** plus real-invocation goldens,
> with Typer's help/unknown-command chrome excluded by name; and the Typer
> dependency (revising the stdlib-plus-PyYAML posture, including its cost to
> the zero-install source paths) is isolated in its own phase, **droppable
> without orphaning the split**.
>
> Sequencing is load-bearing: R0 → R1 → R2 (package split, still argparse) →
> R3 (Typer swap) → R4 (module regroup). No phase begins until the previous
> phase's claims are closed and the fleet gate is green.

---

## R0 — Differential equivalence against the pinned pre-refactor engine

**Purpose.** Before any file moves, arm a harness that answers the only
question that matters throughout: *does the reorganized engine behave exactly
like the engine everyone currently trusts?* The reference is not a
hand-curated golden but the **pre-refactor engine itself**, built from a pinned
git ref into a temporary worktree and run side-by-side with the working tree on
identical fixtures. The R0 claim closes at arming (working tree ≡ baseline,
trivially) and from then on acts as a **regression guard for the entire
migration**: any behavioral drift in any later phase turns it RED and blocks
the gate.

**Contract.**

- **R0.1 Side-by-side differential roster, outputs and exit codes.** A probe
  shall materialize the pinned baseline engine (git worktree of the recorded
  ref), run a fixed roster of commands with both engines against identical
  copies of one fixture project, and assert stdout, stderr, and exit code are
  byte-equal after normalizing durations, absolute paths, and timestamps. The
  roster must cover at least: `ledger`, `validate`, `matrix`, `matrix --gate`,
  `stats`, `trajectories`, `frontier`, `coverage`, and at least one
  engine-emitted error path (e.g. `report --narrate` with no configured
  narrator).
  - *Observable:* on an untouched tree the probe exits 0 (self ≡ baseline);
    with any rostered command whose output or exit code differs between the
    two engines it exits nonzero naming the first divergent command.
  - *Counterexample (wrong):* a harness that compares the working engine
    against itself (both invocations resolving to the same code), or one that
    normalizes so aggressively that a real output change still matches.
  - *Bounded:* the rostered commands on the fixture; normalization is limited
    to the named nondeterministic fields.
- **R0.2 Mutating commands are compared by resulting state.** The roster shall
  also include mutating commands — at minimum `init` (in a scratch dir),
  `baseline`, `record append`, and `pack export` + `pack install` — each run by
  both engines against their own fresh copy of the same fixture, with the
  probe asserting the **resulting fixture trees are equivalent** (same files,
  same normalized contents) in addition to matching output and exit code.
  - *Observable:* both engines baseline the same draft to the same promoted
    ledger bytes (dates normalized); both `init` runs stamp equivalent trees;
    a divergence in any written file is named.
  - *Counterexample (wrong):* a harness that checks only stdout for mutating
    commands, passing while the two engines write different ledgers.
  - *Bounded:* the mutating roster on scratch copies; the real repo's state is
    never touched.
- **R0.3 The baseline pin is explicit, and re-pinning is human-only.** The
  reference ref shall be recorded in a file beside the probe; the harness
  reads it, and a missing or unbuildable ref is BROKEN (exit 2), never a
  verdict. Advancing the pin is a reviewed human act — never part of a cycle
  that also changes engine code.
  - *Observable:* the pin file names one commit; deleting it or naming an
    unfetchable ref makes the probe report BROKEN; the pin's history shows no
    commit that moves the pin and engine code together.
  - *Counterexample (wrong):* a harness that silently falls back to comparing
    against the working tree when the pin is missing, or a cycle that re-pins
    the baseline to its own freshly-changed engine.
  - *Bounded:* the pin file and the reference-materialization step.
- **R0.4 Chrome is out of the contract, by name.** The roster must exclude
  `--help` output and unknown-command errors, so the later Typer phase is free
  to change that chrome while R0 stays green. Engine-emitted errors remain in
  the contract.
  - *Observable:* the roster names only real invocations and engine error
    paths; help/unknown-command surfaces appear nowhere in the comparison.
  - *Counterexample (wrong):* a roster that pins argparse's help layout, so
    the harness turns RED on the framework swap instead of on behavior.
  - *Bounded:* the two chrome surfaces and nothing else.

## R1 — Golden characterization harness (the guardian that outlives the pin)

**Purpose.** R0 dies with the migration (its pin retires when the reorg
lands). R1 pins the observable contract durably: captured goldens per command,
so any *future* change that shifts real-invocation output turns RED — the same
instrument, anchored to recorded bytes instead of a reference engine.

**Contract.**

- **R1.1 A determinism-safe command roster is pinned to a golden.** A probe
  shall run the read-only roster (`ledger`, `validate`, `matrix`,
  `matrix --gate`, `trajectories`, `stats`, `frontier`, `coverage`) against
  one built fixture project and must assert each command's stdout and exit
  code equal a captured golden, with duration, absolute-path, and timestamp
  fields normalized before the comparison.
  - *Observable:* on the fixture the probe exits 0 when every rostered command
    matches its golden, and exits nonzero naming the first command whose bytes
    or exit code drifted.
  - *Counterexample (wrong):* a harness that stays GREEN when a rostered
    command's output changed, or that pins a raw duration field so the golden
    can never match twice.
  - *Bounded:* the rostered read-only commands on one fixture.
- **R1.2 Framework chrome is out of the contract, by name.** Same exclusion as
  R0.4: help and unknown-command chrome are not compared; engine-emitted
  errors are.
  - *Observable:* the roster names only real command invocations.
  - *Counterexample (wrong):* a golden of argparse's `--help` that turns RED
    the moment Typer renders its own.
  - *Bounded:* the two chrome surfaces.

## R2 — cli.py becomes a package (still argparse; split before swap)

**Purpose.** The first structural move, isolated from the framework change:
the 1,586-line monolith becomes a package — a thin `cli/main.py` holding the
argparse assembly and shared helpers (`_config`, `_load`, `_fail`), and one
module per command under `cli/commands/`. Because the dispatcher is untouched,
any R0 divergence in this phase is attributable to the *split*, not the
framework.

**Contract.**

- **R2.1 The monolith is gone; commands live one per module.**
  `recurvelib/cli.py` must not remain a single module file; `recurvelib/cli/`
  shall be a package holding `main.py` plus one `commands/<name>.py` per
  command, and no file under `recurvelib/cli/` may exceed 400 lines.
  - *Observable:* `recurvelib/cli/` is a directory package, each command
    resolves to its own module under `cli/commands/`, and the largest file
    under `recurvelib/cli/` is at most 400 lines.
  - *Counterexample (wrong):* a `cli/` package that imports a still-present
    1,586-line module (the monolith relocated, not split), or a `commands/`
    directory holding one god-module.
  - *Bounded:* the `recurvelib/cli/` package tree.
- **R2.2 The console entrypoint is unchanged.** `recurvelib.cli:main` must stay
  importable and callable, so the `recurve` console script and the repo-root
  `recurve` wrapper both dispatch every command.
  - *Observable:* `from recurvelib.cli import main` succeeds, and both
    `recurve validate` and `python3 recurve validate` run and exit 0 on the
    self-host tree.
  - *Counterexample (wrong):* a move that relocates `main` so
    `recurvelib.cli:main` no longer resolves, breaking the `pyproject`
    console-script entrypoint.
  - *Bounded:* the `recurvelib.cli:main` import path and the two invocation
    paths.
- **R2.3 The split lands with R0 green.** This phase changes no dispatcher, no
  flag, no output: R0's differential harness and the 29 CLI-shelling probes
  must hold byte-for-byte across the split, including help and
  unknown-command chrome (argparse is still the framework, so even the chrome
  is unchanged in this phase).
  - *Observable:* R0 green, fleet gate green, and `recurve --help` output
    identical to the pinned baseline's (this phase only).
  - *Counterexample (wrong):* a split that reorders help text or shifts an
    error message — behavior change smuggled in as structure.
  - *Bounded:* every command surface, chrome included, for this phase alone.

## R3 — Typer becomes the dispatcher (separable; the posture cost is priced)

**Purpose.** With the split landed and proven inert, the framework swap is a
small, isolated diff: `main.py` and per-command argument declarations move to
Typer; command bodies do not change. This phase is **droppable** — if the
maintainer declines the dependency, R2's navigability stands on argparse.

**The priced cost, on the record:** `typer` joins PyYAML as a declared runtime
dependency, revising the stdlib-plus-PyYAML posture. This is not only a
`pyproject` line: the zero-install source paths — the repo-root `recurve`
wrapper, the `recurve install` symlink, and every probe invoking
`python3 $RECURVE` — then require typer importable in whatever environment
runs them (CI, agent sandboxes, fresh clones). Accepting that trade is the
maintainer's call, made here, visibly.

**Contract.**

- **R3.1 Typer is the dispatcher and a declared dependency.** The CLI layer
  must dispatch through Typer with no `import argparse` under
  `recurvelib/cli/`, and `typer` shall be declared in `pyproject.toml`
  dependencies.
  - *Observable:* `recurvelib/cli/` imports `typer` and contains no
    `import argparse`; `pyproject.toml` lists `typer`; a fresh
    `pip install -e .` resolves and runs the `recurve` entrypoint.
  - *Counterexample (wrong):* argparse still dispatching with Typer imported
    but unused, or Typer used without the declared dependency so a fresh
    install crashes on first run.
  - *Bounded:* the `recurvelib/cli/` package and `pyproject.toml`.
- **R3.2 Real-invocation behavior survives the swap.** R0's differential
  harness (which excludes chrome) and the 29 CLI-shelling probes must stay
  green across the swap; engine-emitted errors keep their text and exit codes
  (e.g. `report --narrate` with no narrator still prints the engine's usage
  error and exits 2); Typer's native help and unknown-command errors replace
  argparse's.
  - *Observable:* R0 green post-swap; the narrator error is byte-identical
    with exit 2; help output is Typer's (not compared).
  - *Counterexample (wrong):* a command whose JSONL, report, or matrix bytes
    shifted under Typer, or an engine error whose exit code changed to a
    framework default.
  - *Bounded:* real invocations and engine-emitted errors; chrome excluded by
    name.
- **R3.3 Captured output carries no framework color or chrome.** Under a pipe
  or with `NO_COLOR` set, Typer must emit no ANSI styling into stdout or
  stderr, so captured and piped output stays plain for the probes that read
  it.
  - *Observable:* `recurve ledger | cat` and a captured run under `NO_COLOR=1`
    contain no ANSI escape introduced by Typer.
  - *Counterexample (wrong):* Typer coloring help or errors and leaking escape
    codes into piped output a downstream probe then fails to match.
  - *Bounded:* stdout and stderr under non-tty capture and `NO_COLOR`.

## R4 — The rest of recurvelib regroups into navigable subpackages

**Purpose.** With the CLI settled, the remaining flat modules gather by
concern. **The probes are part of this move's surface**: 57 probes import flat
module paths (`from recurvelib.controller import …`, `.admission`, `.runtime`,
`.frontier`, `.config`, …) — they are updated in the same change, mechanically,
and the updated fleet plus R0 prove nothing else moved.

**Contract.**

- **R4.1 Modules group by concern under named subpackages.** The remaining
  top-level modules must move under a small set of concern subpackages — the
  proposed map: `core/` for the domain model and verification primitives
  (`model`, `probe`, `conformance`, `freshness`, `baseline`), `runtime/` for
  the loop, world adapters, and lock (`run`, `controller`, `runtime`,
  `adapters`, `lock`, `cycle`), and `io/` for persistence, scaffolding, and
  reporting (`records`, `receipts`, `pack`, `importer`, `report`, `render`,
  `init`) — each with an `__init__.py`, and the count of loose `.py` files
  directly under `recurvelib/` shall drop to at most three.
  - *Observable:* `recurvelib/` holds named subpackages plus at most three
    loose modules, every moved module resolves under its subpackage, and
    `recurve validate` runs.
  - *Counterexample (wrong):* a regroup that dumps modules into a `misc/` or
    `util/` junk-drawer, or that leaves the flat ~30-module top level intact
    behind package aliases.
  - *Bounded:* the `recurvelib/` top-level module layout.
- **R4.2 Probe imports move in the same change, import-lines only.** Every
  probe (and trap fixture) importing a moved module shall be updated to the
  new path **in the same commit as the move**, with the diff to each probe
  limited to import statements — assertions, fixtures, and traps are
  untouched, and the full fleet gate plus every trap re-proves RED afterward.
  Updating an import path to follow a moved module is maintenance, not
  weakening; anything beyond the import lines is out of bounds.
  - *Observable:* post-move, the probe diffs touch only `import`/`from` lines;
    `recurve matrix --gate` is green with every trap still RED; no probe
    remains importing a retired flat path.
  - *Counterexample (wrong):* a probe whose assertion or trap changed in the
    same commit as the move, or a moved module left aliased at top level so
    probes never had to follow.
  - *Bounded:* import statements in the 57 affected probes and any trap
    fixtures that import moved modules.
- **R4.3 Every internal import resolves after the move.** Every internal
  import path must update to the new locations, so no module raises
  `ImportError` and the full fleet gate runs green.
  - *Observable:* importing `recurvelib` and running `recurve matrix --gate`
    on the self-host tree resolves every module and prints `GATE OK`.
  - *Counterexample (wrong):* a moved module whose old import path a caller
    still uses, crashing a command at runtime.
  - *Bounded:* internal import paths across `recurvelib`.
- **R4.4 Shipped-resource resolution survives the move.**
  `recurvelib.resource_dir` must still resolve the `templates`, `schema`, and
  `packs` trees, so `init`, receipts, and the schemas keep loading from both a
  source checkout and an installed wheel.
  - *Observable:* after the regroup, `recurve init` in a temp dir stamps its
    templates and `recurve record append` validates against the shipped
    schema.
  - *Counterexample (wrong):* a move that relocates `resource_dir`'s anchor so
    `_assets` no longer resolves, breaking `init` or schema loading in an
    installed wheel.
  - *Bounded:* `recurvelib.resource_dir` and the three resource trees.

---

## Non-goals (this PRD)

- No change to any command's real-invocation output, flags, arguments, or exit
  codes — this work is structure and framework, never behavior.
- No command-surface reduction, renaming, or verb-count redesign — that
  ambition lives in `command-improvements`, not here.
- No new engine feature and no changed claim, probe, or gate semantics.
- No reproduction of argparse's help and usage chrome in R3 — Typer's native
  help and errors are adopted on purpose (R2 keeps chrome identical, because
  argparse is still the framework there).
- No public Python API promise beyond the `recurve` console entrypoint,
  `recurvelib.cli:main`, and per-command CLI behavior — internal import paths
  may move, with R4.2 governing the probes that follow them.

## Forbidden (negative space)

- **No phase lands while R0 is red**, and no phase begins before the previous
  phase's claims are closed under a green fleet gate.
- The baseline pin is never advanced in a commit that also changes engine
  code — re-pinning is a reviewed, human-only act.
- The `recurve` console entrypoint and `recurvelib.cli:main` must never break.
- No command's real-invocation stdout, stderr, or exit code may drift, and the
  engine's own error text and exit codes must survive verbatim.
- No probe assertion or trap may change to accommodate a move — R4.2's
  import-line updates are the sole permitted probe diff, and every trap must
  re-prove RED after them.
- `recurvelib.resource_dir` must never stop resolving the `templates`,
  `schema`, and `packs` trees.
- No module may be relocated into a `misc` or `util` junk-drawer.
- Typer must never leak ANSI color or rich chrome into piped or captured
  output.
