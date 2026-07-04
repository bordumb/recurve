# reorg — recurvelib reorganization and a Typer CLI

The promises of `docs/plans/recurvelib-reorg-and-typer.md`, probed. This is
surgery on the judge, so the safety case is measured, not assumed: the engine
is refactored (CLI split, framework swap, module regroup) with **zero change to
what any command does**, and the differential harness below is the arbiter of
that.

Convention: every reorg probe compares the working engine against a **pinned
pre-refactor engine** — a `git archive` of `BASELINE_REF` extracted into a temp
dir and run side-by-side on identical fixtures. `BASELINE_REF` is advanced only
by a reviewed human act, never in a commit that also changes engine code.

## R0-1 — differential read-only roster (outputs + exit), chrome excluded

The harness materializes the pinned baseline engine and runs a fixed read-only
roster (`ledger`, `validate`, `matrix`, `matrix --gate`, `stats`,
`trajectories`, `frontier`, `coverage`, and the `report --narrate` engine-error
path) with both the baseline and the working engine against identical fixture
state, asserting byte-equal normalized stdout+stderr+exit. On an untouched tree
the two engines are the same code, so the roster agrees (GREEN); any later phase
that drifts turns this RED naming the first divergent command. Chrome is out of
the contract by name — the roster carries an engine-emitted error path and never
`--help` or an unknown-command surface — so the Typer phase may change that
chrome freely. Covers PRD R0.1 and R0.4. Negative space (guarded by the trap): a
harness that passes a sabotaged, divergent engine as equivalent.

## R0-2 — mutating commands compared by resulting state

For `init`, `baseline`, `record append`, and `pack export`, both engines run
against their own fresh copy of the same fixture, and the probe asserts the
resulting fixture trees are equivalent (same files, same root-normalized
contents) in addition to matching output and exit. A stdout-only check would
pass while two engines wrote different ledgers; comparing resulting state closes
that gap. Covers PRD R0.2. Negative space (guarded by the trap): a check that
misses an engine writing an extra file — a state divergence invisible to stdout.

## R0-3 — the baseline pin is explicit, and re-pinning is human-only

The reference ref lives in `BASELINE_REF` beside the probes; the harness reads
it, and a missing or unbuildable ref is BROKEN (exit 2), never silently
downgraded to comparing the engine against itself. The pin is advanced only by a
reviewed human act: no commit in history touches both the pin file and engine
code (`recurvelib/`, `recurve`, `pyproject.toml`). Covers PRD R0.3. Negative
space (guarded by the trap): a harness that accepts a bogus, unbuildable pin as
a valid baseline instead of reporting BROKEN.

## R1-1 — golden characterization harness (durable, chrome excluded)

The guardian that outlives R0's pin. R0 dies with the migration (its baseline
ref retires once the reorg lands); R1 pins the observable contract durably, as
captured golden bytes per command under `golden/`, so any future change that
shifts real-invocation output turns RED. Same read-only roster and same chrome
exclusion as R0, but anchored to recorded bytes instead of a reference engine. A
missing golden is BROKEN, never a silent pass. Covers PRD R1.1 and R1.2.
Negative space (guarded by the trap): a comparison that waves a corrupted golden
through as a match.

## R2-1 — cli.py becomes a package (argparse intact), entrypoint survives

`recurvelib/cli.py` is no longer a single 1,586-line module: `recurvelib/cli/`
is a package holding `main.py` (the argparse assembly + shared helpers) plus one
module per command under `commands/`, with no file over 400 lines, and
`recurvelib.cli:main` stays importable so the `recurve` console script and the
repo wrapper still dispatch. The dispatcher is untouched (still argparse), so
this phase changes no flag and no output — behavioral inertness is enforced by
the standing R0/R1 guards the fleet gate runs. Covers PRD R2.1 and R2.2.
Negative space (guarded by the trap): a `cli/` package that merely relocated the
monolith into one oversized module.

## R3-1 — Typer becomes the dispatcher (declared dependency)

The CLI layer dispatches through Typer with no `import argparse` anywhere under
`recurvelib/cli/`, and `typer` is a declared runtime dependency in
`pyproject.toml`, so a fresh install resolves and runs the entrypoint. The
command bodies are unchanged — only the dispatch and argument-declaration layer
moves. Real-invocation behavior is held by the standing R0/R1 guards + the CLI
probes; Typer's native help and unknown-command errors replace argparse's.
Covers PRD R3.1 and R3.2. Negative space (guarded by the trap): a `cli/` that
imports typer but leaves argparse dispatching (imported but unused).

## R3-2 — no framework color or chrome leaks into captured output

Under a pipe or with `NO_COLOR` set, the CLI emits no ANSI styling into stdout
or stderr — a real Typer/click gotcha — so captured and piped output stays plain
for the probes that read it. Covers PRD R3.3. Negative space (guarded by the
trap): a detector that misses an ANSI escape in captured output.
