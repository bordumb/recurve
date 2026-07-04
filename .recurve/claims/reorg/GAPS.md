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
