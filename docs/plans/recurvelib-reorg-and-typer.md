# PRD — recurvelib reorganization and a Typer-native CLI

> Source: the engine has grown a monolith. `recurvelib/cli.py` is 1,586 lines —
> 31 `cmd_*` functions and ~30 subcommands dispatched by one hand-assembled
> argparse tree in `main()`, more than four times the next-largest module. The
> goal here is navigability for future contributors: split the CLI monolith into
> a package a reader can hold in their head, adopt Typer as the dispatcher, and
> regroup the remaining flat modules by concern — all with **zero change to what
> any command does**. The gate rests on behavioral equivalence: 164 probes, 42
> of which shell out to the CLI, plus the fleet gate, are the arbiter that the
> reorg preserved behavior. No probe today asserts on argparse's `--help` or
> usage chrome, and none greps a `recurvelib/*.py` source path, so the framework
> swap and the file moves are achievable under the gate. Three decisions, taken
> with the maintainer: the CLI package arrives Typer-native in one move (not a
> split-then-swap); the equivalence contract is **real-invocation exact** (every
> command's output and exit code held byte-for-byte, Typer's native help and
> errors adopted); and Typer joins PyYAML as a declared runtime dependency,
> revising the prior stdlib-plus-PyYAML posture on purpose.

---

## R1 — Real-invocation equivalence is pinned by a characterization harness

**Purpose.** A refactor is behavior-preserving only if "behavior" is measured
before the code moves. Most commands already have a probe that would turn RED on
an output change, but not all do. R1 adds one guardian that pins the observable
contract of the real CLI — a captured golden per command — so any later move
that shifts real-invocation output turns this probe RED. "Real invocation" is
the roster of commands a user runs for a result; the framework's `--help` and
unknown-command chrome are deliberately outside the roster.

**Contract.**

- **R1.1 A determinism-safe command roster is pinned to a golden.** A probe
  shall run a fixed roster of read-only commands (`ledger`, `validate`,
  `matrix`, `matrix --gate`, `trajectories`, `stats`, `frontier`, `coverage`)
  against one built fixture project and must assert each command's stdout and
  exit code equal a captured golden, with duration, absolute-path, and
  timestamp fields normalized before the comparison.
  - *Observable:* on the fixture the probe exits 0 when every rostered command
    matches its golden stdout and exit code, and exits nonzero naming the first
    command whose bytes or exit code drifted.
  - *Counterexample (wrong):* a harness that stays GREEN when a rostered
    command's output changed, or that pins a raw duration field so the golden
    can never match twice.
  - *Bounded:* the rostered read-only commands on one fixture; the normalized
    nondeterministic fields are the only bytes excluded from the comparison.
- **R1.2 Framework chrome is out of the contract, by name.** The harness must
  exclude `--help` output and unknown-command errors from its roster, so the
  Typer swap is free to change that chrome while the harness stays GREEN.
  - *Observable:* the roster names only real command invocations; adding
    `recurve --help` or `recurve bogus` to the compared set is what the harness
    forbids, not what it checks.
  - *Counterexample (wrong):* a harness that pins argparse's `--help` layout and
    so turns RED the moment Typer renders its own help.
  - *Bounded:* the two chrome surfaces — top-level/command help and the
    unknown-command error — and nothing else.

## R2 — cli.py becomes a Typer-native cli/ package

**Purpose.** The 1,586-line argparse monolith becomes a package a contributor
navigates by command: a thin `cli/main.py` that assembles the Typer app and the
shared helpers (`_config`, `_load`, `_fail`), and one module per command under
`cli/commands/`. The console entrypoint and every command's real-invocation
behavior are preserved; Typer's native help and errors are adopted.

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
  - *Observable:* `from recurvelib.cli import main` succeeds, and both `recurve
    validate` and `python3 recurve validate` run and exit 0 on the self-host
    tree.
  - *Counterexample (wrong):* a move that relocates `main` so
    `recurvelib.cli:main` no longer resolves, breaking the `pyproject`
    console-script entrypoint.
  - *Bounded:* the `recurvelib.cli:main` import path and the two invocation
    paths.
- **R2.3 Typer is the dispatcher and a declared dependency.** The CLI layer must
  dispatch through Typer with no `import argparse` under `recurvelib/cli/`, and
  `typer` shall be declared in `pyproject.toml` project dependencies.
  - *Observable:* `recurvelib/cli/` imports `typer` and contains no `import
    argparse`; `pyproject.toml` lists `typer` under `dependencies`; a fresh
    install resolves the `recurve` entrypoint.
  - *Counterexample (wrong):* a `cli/` package that still dispatches via
    argparse with Typer imported but unused, or Typer used without the declared
    dependency so a fresh install crashes on first run.
  - *Bounded:* the `recurvelib/cli/` package and `pyproject.toml` dependencies.
- **R2.4 Every command's real-invocation output and exit code are preserved.**
  For every command, stdout, stderr, and exit code on a real invocation must
  equal the pre-refactor bytes, and the engine's own error messages (for
  instance a missing narrator's usage error) shall keep their text and exit
  code; Typer's native help layout and unknown-command errors replace
  argparse's.
  - *Observable:* the R1 harness stays GREEN across the swap, the 42
    CLI-shelling probes stay GREEN, and `recurve report --narrate` with no
    configured narrator still prints its engine usage error and exits 2.
  - *Counterexample (wrong):* a command whose JSONL, report, or matrix bytes
    shifted under Typer, or an engine error whose exit code changed from 2 to
    Typer's default.
  - *Bounded:* real command invocations and engine-emitted errors; argparse's
    synthetic help and usage chrome is excluded by name.
- **R2.5 Captured output carries no framework color or chrome.** Under a pipe or
  with `NO_COLOR` set, Typer must emit no ANSI styling into stdout or stderr, so
  captured and piped output stays plain for the probes that read it.
  - *Observable:* `recurve ledger | cat` and a captured run under `NO_COLOR=1`
    contain no ANSI escape sequence introduced by Typer.
  - *Counterexample (wrong):* Typer coloring help or errors and leaking escape
    codes into piped output a downstream probe then fails to match.
  - *Bounded:* stdout and stderr under non-tty capture and `NO_COLOR`.

## R3 — The rest of recurvelib regroups into navigable subpackages

**Purpose.** With the CLI split done, the remaining flat modules gather by
concern into named subpackages, so a contributor navigates `recurvelib` by what
a module does rather than by scanning ~30 sibling files. Behavior, entrypoints,
and shipped-resource loading are untouched — this phase moves files and rewrites
import paths, nothing else.

**Contract.**

- **R3.1 Modules group by concern under named subpackages.** The remaining
  top-level modules must move under a small set of concern subpackages — the
  proposed map: `core/` for the domain model and verification primitives
  (`model`, `probe`, `conformance`, `freshness`, `baseline`), `runtime/` for the
  loop, world adapters, and lock (`run`, `controller`, `runtime`, `adapters`,
  `lock`, `cycle`), and `io/` for persistence, scaffolding, and reporting
  (`records`, `receipts`, `pack`, `importer`, `report`, `render`, `init`) — each
  with an `__init__.py`, and the count of loose `.py` files directly under
  `recurvelib/` shall drop to at most three.
  - *Observable:* `recurvelib/` holds named subpackages plus at most three loose
    modules, every moved module resolves under its subpackage, and `recurve
    validate` runs.
  - *Counterexample (wrong):* a regroup that dumps modules into a `misc/` or
    `util/` junk-drawer, or that leaves the flat ~30-module top level intact
    behind package aliases.
  - *Bounded:* the `recurvelib/` top-level module layout.
- **R3.2 Every import resolves after the move.** Every internal import path must
  update to the new module locations, so no module raises `ImportError` and the
  full fleet gate runs green.
  - *Observable:* importing `recurvelib` and running `recurve matrix --gate` on
    the self-host tree resolves every module and prints `GATE OK`, with no
    `ModuleNotFoundError`.
  - *Counterexample (wrong):* a moved module whose old import path a caller
    still uses, crashing a command at runtime.
  - *Bounded:* internal import paths across `recurvelib`.
- **R3.3 Shipped-resource resolution survives the move.**
  `recurvelib.resource_dir` must still resolve the `templates`, `schema`, and
  `packs` trees, so `init`, receipts, and the schemas keep loading from both a
  source checkout and an installed wheel.
  - *Observable:* after the regroup, `recurve init` in a temp dir stamps its
    templates and `recurve record append` validates against the shipped schema;
    both resolve their resource trees.
  - *Counterexample (wrong):* a move that relocates `resource_dir`'s anchor so
    `_assets` no longer resolves, breaking `init` or schema loading in an
    installed wheel.
  - *Bounded:* `recurvelib.resource_dir` and the `templates`, `schema`, `packs`
    resource trees.

---

## Non-goals (this PRD)

- No change to any command's real-invocation output, flags, arguments, or exit
  codes — this work is structure and framework, never behavior.
- No command-surface reduction, renaming, or verb-count redesign — that ambition
  lives in `command-improvements`, not here.
- No new engine feature and no changed claim, probe, or gate semantics.
- No reproduction of argparse's help and usage chrome — Typer's native help and
  errors are adopted on purpose.
- No public Python API promise beyond the `recurve` console entrypoint,
  `recurvelib.cli:main`, and per-command CLI behavior — internal import paths are
  free to move.

## Forbidden (negative space)

- The `recurve` console entrypoint and `recurvelib.cli:main` must never break — a
  refactor that severs the entrypoint fails, however navigable the tree looks.
- No command's real-invocation stdout, stderr, or exit code may drift, and the
  engine's own error text and exit codes must survive verbatim.
- No probe may be weakened and no trap may be edited to accommodate a move — a
  GREEN must mean behavior held.
- `recurvelib.resource_dir` must never stop resolving the `templates`, `schema`,
  and `packs` trees.
- No module may be relocated into a `misc` or `util` junk-drawer that relocates
  the monolith instead of resolving it.
- Typer must never leak ANSI color or rich chrome into piped or captured output.
